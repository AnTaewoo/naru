"""노선 경로(getRoutePath) — 버스 위치를 노선 위에 놓는 부품. 확신도 보정은 뺐다(ADR-013 보류,
태우 2026-11-09: 1개 차로 행진에서 버스 152회 정상 통과 — 차로 신호라 횡단보도 막힘을 모른다).

쓰는 곳: scripts/eval_bus_20261109.py(11/9 실측, docs/eval/bus_20261109.md), 2027
서울마라톤의 정류소 건너뜀 분석(README "앞으로"). 노선 경로는 raw
`bus_routes/<날짜>/path_<노선>.json`(정점 순서 = 운행 순서). 구간 = 통제 횡단보도 중 노선
30 m 안의 것들의 노선 위 범위 — 같은 길을 오가는 노선은 지나는 번마다 하나. 버스 좌표는
노선에 맞춘 값이다(11/9 통제 구간 노선 관측 9,429건 모두 경로 32.7 m 안) — 경로에서
벗어남으로는 우회를 못 본다.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer

_4326_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

NEAR_ROUTE_M = 30.0  # 구간 = 통제 횡단보도 중 노선 30 m 안
PASS_GAP_M = 500.0  # 노선 위 횡단보도 사이가 이보다 멀면 다른 지나감(왕복 노선의 가는 길·오는 길)


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
        """통제 횡단보도(ID → EPSG:5179) 중 노선 30 m 안의 것들의 노선 위 범위 — 지나는 번마다 하나.
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
