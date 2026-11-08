"""BusCorrection 부품 (ADR-013, T6.3) — 버스 관측으로 공지 확신도를 보정하는 순수 함수·감지 부품.

보정 표(ADR-013 A):
- 서로 다른 2대 이상이 15분 안에 구간을 피해 감 +0.20 (근거 bus_skip)
- 구간 정류소를 2대 이상 건너뜀 +0.10 · 통과 시간이 평소 2배 초과 2대 이상 +0.10
- 1대만 피해 감 +0.05 · 2대 이상이 평소 속도(1.3배 이내)로 정상 통과 -0.30
- 합은 [-0.30, +0.25], 최종 = clamp(공지 + 합, 0, 0.95)

시각의 함수: (at - 20분, at] 관측만. 정상 통과가 든 평가가 20분 넘게 이어지면 그때 해제
(bus_return), 그 뒤 2대 이탈이면 무른다. 노선 경로는 getRoutePath(raw `bus_routes/<날짜>/
path_<노선>.json`, 정점 순서 = 운행 순서). 구간 = 후보 횡단보도 중 노선 30 m 안의 것들의 노선 위
범위 — 같은 길을 오가는 노선은 지나는 번마다 하나.
통제일 버스 기록이 아직 없어 여기까지다(ADR-013 "실측 대기"): 보정 계열(bus_corrections)·
/closures·/route 적용, 계약(base_confidence·EvidenceKind bus), FE 근거 줄.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from pyproj import Transformer

_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

WINDOW = timedelta(minutes=20)  # 20분 넘은 관측은 빠진다
PAIR_WITHIN = timedelta(minutes=15)  # 서로 다른 2대가 15분 안에 피해 감
OFF_ROUTE_M = 60.0  # 경로에서 이만큼 넘게 벗어난 관측이 2회 연속 = 피해 감
NEAR_ROUTE_M = 30.0  # 구간 = 후보 횡단보도 중 노선 30 m 안
PASS_GAP_M = 500.0  # 노선 위 횡단보도 사이가 이보다 멀면 다른 지나감(왕복 노선의 가는 길·오는 길)
SLOW_FACTOR = 2.0  # 통과 시간이 평소의 2배 초과
NORMAL_FACTOR = 1.3  # 평소 속도 = 통과 시간이 평소의 1.3배 이내
CORRECTION_MIN, CORRECTION_MAX = -0.30, 0.25
FINAL_MAX = 0.95
UNKNOWN_CAP = 0.65  # ADR-008 승격 unknown — 지점 30 m 안 2대 이탈이 살아 있을 때만 넘는다

# 항목 (ADR-013 A) — 이름은 근거 detail.reason
SKIP_PAIR = ("bus_skip", 0.20)
STOP_SKIP = ("stop_skip", 0.10)
SLOW = ("slow", 0.10)
ONE_SKIP = ("one_skip", 0.05)
NORMAL = ("normal_pass", -0.30)


@dataclass(frozen=True)
class Observations:
    """구간 한 번 지나감의 (at - 20분, at] 관측 — 감지 부품이 채운다."""

    skips: dict[str, datetime] = field(default_factory=dict)  # 피해 간 차량 → 피한 시각
    stop_skippers: int = 0  # 구간 안 정류소를 건너뛴 차량 수
    slow: int = 0  # 통과 시간이 평소 2배 초과 (평소가 없으면 0)
    normal: int = 0  # 평소 1.3배 이내로 경로 위 정상 통과 (평소가 없으면 0)


def items(obs: Observations) -> list[tuple[str, float]]:
    """관측 → 보정 항목. 피해 간 차가 있는데 '15분 안 2대'가 아니면(1대, 또는 15분 넘게 떨어진
    여러 대) 약한 근거 +0.05."""
    times = sorted(obs.skips.values())
    out: list[tuple[str, float]] = []
    if any(b - a <= PAIR_WITHIN for a, b in itertools.pairwise(times)):
        out.append(SKIP_PAIR)
    elif times:
        out.append(ONE_SKIP)
    if obs.stop_skippers >= 2:
        out.append(STOP_SKIP)
    if obs.slow >= 2:
        out.append(SLOW)
    if obs.normal >= 2:
        out.append(NORMAL)
    return out


def correction(found: Iterable[tuple[str, float]]) -> float:
    total = sum(delta for _, delta in found)
    return round(min(max(total, CORRECTION_MIN), CORRECTION_MAX), 2)


def final_confidence(
    base: float, corr: float, *, promoted_unknown: bool = False, skip_near_point: bool = False
) -> float:
    """clamp(공지 + 보정, 0, 0.95). 도로 30 m 로 승격된 unknown 은 지점 30 m 안 노선의 2대 이탈이
    살아 있을 때만 0.65 를 넘는다 (ADR-013 B)."""
    cap = UNKNOWN_CAP if promoted_unknown and not skip_near_point else FINAL_MAX
    return round(min(max(base + corr, 0.0), cap), 2)


def recent(times: Iterable[datetime], at: datetime) -> list[datetime]:
    """(at - 20분, at] 의 관측 시각만, 시각 순."""
    return sorted(t for t in times if at - WINDOW < t <= at)


def released_at(evaluations: Sequence[tuple[datetime, Sequence[str]]]) -> datetime | None:
    """평가 계열(시각 순, 항목 이름들) → 지금 해제돼 있으면 해제 시각. 정상 통과가 든 평가가 이어진
    지 20분이 되는 평가에서 해제(bus_return), 그 뒤 2대 이탈(bus_skip)이 잡히면 무른다. 정상 통과가
    빠진 평가가 끼면 처음부터 다시 센다."""
    run_start: datetime | None = None
    released: datetime | None = None
    for at, names in evaluations:
        if released is not None:
            if SKIP_PAIR[0] not in names:
                continue
            released = run_start = None  # 해제를 무른다
        if NORMAL[0] in names:
            run_start = run_start or at
            if at - run_start >= WINDOW:
                released = at
        else:
            run_start = None
    return released


def off_route_twice(distances_m: Sequence[float]) -> bool:
    """한 차량의 시각 순 경로 거리 — 60 m 넘게 벗어난 관측이 2회 연속이면 피해 감."""
    return any(a > OFF_ROUTE_M < b for a, b in itertools.pairwise(distances_m))


def to_5179(lng: float, lat: float) -> tuple[float, float]:
    x, y = _4326_TO_5179.transform(lng, lat)
    return float(x), float(y)


@dataclass(frozen=True)
class RoutePath:
    """getRoutePath 노선 경로 — 정점 순서대로 이은 선(EPSG:5179 m). 노선 위 거리 = 첫 정점부터."""

    route_id: str
    xy: tuple[tuple[float, float], ...]
    start_m: tuple[float, ...]  # 정점마다 노선 위 거리

    @classmethod
    def load(cls, path: Path) -> RoutePath:
        rec = json.loads(path.read_text("utf-8"))
        body = json.loads(rec["raw"]) if isinstance(rec["raw"], str) else rec["raw"]
        if str(body["msgHeader"]["headerCd"]) != "0":
            raise ValueError(f"{path.name}: getRoutePath headerCd {body['msgHeader']['headerCd']}")
        rows = sorted(body["msgBody"]["itemList"], key=lambda r: int(r["no"]))
        xy = tuple(to_5179(float(r["gpsX"]), float(r["gpsY"])) for r in rows)
        start, acc = [0.0], 0.0
        for (ax, ay), (bx, by) in itertools.pairwise(xy):
            acc += math.hypot(bx - ax, by - ay)
            start.append(acc)
        return cls(str(rec["params"]["busRouteId"]), xy, tuple(start))

    @property
    def length_m(self) -> float:
        return self.start_m[-1]

    def _hits(self, x: float, y: float, within: float) -> list[tuple[float, float]]:
        """선분마다 (x, y) 의 가장 가까운 점 — within 안의 것만 (노선 위 거리, 떨어진 거리)."""
        out = []
        for i in range(len(self.xy) - 1):
            (ax, ay), (bx, by) = self.xy[i], self.xy[i + 1]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            t = 0.0 if seg2 == 0 else min(max(((x - ax) * dx + (y - ay) * dy) / seg2, 0.0), 1.0)
            d = math.hypot(x - (ax + t * dx), y - (ay + t * dy))
            if d <= within:
                out.append((self.start_m[i] + t * math.sqrt(seg2), d))
        return out

    def distance_m(self, x: float, y: float) -> float:
        """경로까지 거리 (EPSG:5179)."""
        hits = self._hits(x, y, math.inf)
        return min(d for _, d in hits) if hits else math.inf

    def near_measures(self, x: float, y: float, within: float = NEAR_ROUTE_M) -> list[float]:
        """노선이 (x, y) 를 within 안으로 지나는 곳마다 노선 위 거리 — 같은 길을 두 번 지나면 둘.
        이웃 선분의 같은 지나감은 가장 가까운 하나로."""
        out: list[tuple[float, float]] = []
        for m, d in sorted(self._hits(x, y, within)):
            if out and m - out[-1][0] <= 2 * within:
                if d < out[-1][1]:
                    out[-1] = (m, d)
                continue
            out.append((m, d))
        return [m for m, _ in out]

    def passes(self, points: Mapping[str, tuple[float, float]]) -> list[tuple[float, float]]:
        """후보 횡단보도(ID → EPSG:5179) 중 노선 30 m 안의 것들의 노선 위 범위 — 지나는 번마다 하나.
        노선 위로 500 m 넘게 떨어지거나 같은 횡단보도가 또 나오면(되돌아 나오는 노선) 새로."""
        hits = sorted((m, key) for key, (x, y) in points.items() for m in self.near_measures(x, y))
        out: list[tuple[float, float]] = []
        seen: set[str] = set()
        for m, key in hits:
            if out and m - out[-1][1] <= PASS_GAP_M and key not in seen:
                out[-1] = (out[-1][0], m)
                seen.add(key)
            else:
                out.append((m, m))
                seen = {key}
        return out
