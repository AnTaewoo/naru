"""11/9 통제일 버스 기록 평가 — ADR-013 보류의 근거(docs/eval/bus_20261109.md). 읽기만.

    uv run python scripts/eval_bus_20261109.py        # 표를 markdown 으로

통제 = 그날 실제 통제 셋(국회대로 1109233·강남대로 1109234 돌발, 하나증권 공지 smpa-20261109-r01)의
횡단보도. 기록으로 다시 만든다: 테스트 DB(naru_test)에 실제 앱을 띄우고 워커 발행 경로로 공지
(sentences.jsonl, LLM 기록 재생)·돌발(recorded incident 20261109T145523 AccInfo, 링크
기록)을 싣고
/closures 를 묻는다 — 운영 DB 는 안 건드린다. 노선 경로 raw bus_routes/20261109, 정류소 순번 raw
OA-1095, 버스 위치 recorded bus/{notice,incident}/20261109T*.
버스의 노선 위 거리 = 정류소 순번(sectOrd)의 노선 위 거리 + sectDist(왕복 노선의 가는 길·오는
길을 좌표로 헷갈리지 않게). 경로까지 거리 = GPS 와 경로선의 최단 거리(EPSG:5179).
통과 = 한 차량이 구간(통제 횡단보도 30 m 안 노선 범위 ± 50 m) 앞 관측에서 20분 안에 구간 뒤 관측으로
간 것. 속도는 그 두 관측 사이 노선 위 평균(정차 포함).
"""

from __future__ import annotations

import itertools
import json
import statistics
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from openpyxl import load_workbook

from naru_ai.config import Settings as AISettings
from naru_ai.publish import CandidatePublisher
from naru_ai.worker import IngestWorker
from naru_be.app import create_app
from naru_be.config import Settings
from naru_be.models.domain.bus_route import RoutePath, to_5179

KST = timezone(timedelta(hours=9))
DAY = "20261109"
ACCINFO = "20261109T145523_AccInfo.json"  # 1109233·1109234 가 다 있는 마지막 돌발 기록
OFF_ROUTE_M = 60.0  # ADR-013 "피해 감" 기준 — 2회 연속
MARGIN_M = 50.0
WITHIN = timedelta(minutes=20)
JUMP_KMH = 60.0  # 관측 사이 노선 위 속도가 이보다 빠르면 정류소 순번이 끊긴 것으로 본다
# (통제 reason 앞부분, 그 통제로 부른 노선) — 워커 로그 bus routes·bus incident route (11/9)
CONTROLS = [
    ("rally 국회대로", ["100100032"], "2026-11-09T12:00:00+09:00"),
    ("10:30~13:00 하나증권", ["100100032", "100100034", "100100043"], "2026-11-09T12:00:00+09:00"),
    ("rally 강남대로", ["100100500"], "2026-11-09T14:30:00+09:00"),
]


@dataclass
class Obs:
    veh: str
    plate: str
    tm: datetime
    m: float
    d: float
    sect: int
    stop: bool
    last: str


def controls(root: Path) -> dict[str, tuple[dict, dict[str, tuple[float, float]]]]:
    """통제 reason → (창, 횡단보도 점) — naru_test 에 기록을 실어 /closures 로."""
    base = Settings()
    if not base.test_database_url.endswith("/naru_test"):
        raise SystemExit("naru_test 가 아니다 — 운영 DB 를 쓰지 않는다")
    app = create_app(Settings(DATABASE_URL=base.test_database_url, internal_token="naru-eval"))
    models = app.extensions["naru"]
    models.repo.truncate()
    http = httpx.Client(transport=httpx.WSGITransport(app=app), base_url="http://naru.eval")
    pub = CandidatePublisher("http://naru.eval", "naru-eval", client=http, backoff_s=0.0)
    ai = AISettings(
        NARU_INCIDENT_RECORD=str(root / "recorded" / "incident" / ACCINFO),
        NARU_SMPA_DIR=tempfile.mkdtemp(),
    )
    worker = IngestWorker(ai, pub)
    worker.run_once(include_course=False)
    pub.publish(worker.incident_batch())
    out: dict[str, tuple[dict, dict[str, tuple[float, float]]]] = {}
    client = app.test_client()
    for prefix, _, at in CONTROLS:
        q = {"bbox": "126.79,37.43,127.19,37.70", "at": at}
        for f in client.get("/closures", query_string=q).get_json()["features"]:
            p = f["properties"]
            if p["reason"].startswith(prefix):
                win = out.setdefault(prefix, (p["window"], {}))
                win[1][p["crosswalk_id"]] = tuple(f["geometry"]["coordinates"])
    models.repo.truncate()
    return out


def stops_of(root: Path, routes: set[str]) -> dict[str, list[tuple[int, str, str, float, float]]]:
    xlsx = root / "raw" / "bus_routes_20261108" / "OA-1095.xlsx"
    rows = load_workbook(xlsx, read_only=True).worksheets[0].iter_rows(values_only=True)
    head = [str(c) for c in next(rows)]
    rid, seq, node, name = (head.index(n) for n in ("ROUTE_ID", "순번", "NODE_ID", "정류소명"))
    x, y = head.index("X좌표"), head.index("Y좌표")
    out: dict[str, list[tuple[int, str, str, float, float]]] = defaultdict(list)
    for r in rows:
        if str(r[rid]) in routes:
            out[str(r[rid])].append(
                (int(str(r[seq])), str(r[node]), str(r[name]), float(str(r[x])), float(str(r[y])))
            )
    return {k: sorted(v) for k, v in out.items()}


def stop_measures(
    rp: RoutePath, stops: list[tuple[int, str, str, float, float]]
) -> dict[int, float]:
    """정류소 순번 → 노선 위 거리: 앞 정류소보다 뒤에서 가장 앞(60 m, 없으면 300 m 안)."""
    out: dict[int, float] = {}
    prev = -1.0
    for seq, _, _, lng, lat in stops:
        x, y = to_5179(lng, lat)
        for within in (60.0, 300.0):
            ms = [m for m in rp.near_measures(x, y, within) if m >= prev - 30]
            if ms:
                prev = min(ms)
                out[seq] = prev
                break
    return out


def observations(root: Path, route: str, rp: RoutePath, sm: dict[int, float]) -> list[Obs]:
    seen: set[tuple[str, str]] = set()
    out: list[Obs] = []
    for kind in ("notice", "incident"):
        for f in sorted(
            (root / "recorded" / "bus" / kind).glob(f"{DAY}T*_getBusPosByRtid_{route}.json")
        ):
            body = json.loads(json.loads(f.read_text("utf-8"))["raw"])
            for it in body["msgBody"]["itemList"] or []:
                key = (it["vehId"], it["dataTm"])
                base = sm.get(int(it["sectOrd"]))
                if key in seen or base is None:
                    continue
                seen.add(key)
                x, y = to_5179(float(it["gpsX"]), float(it["gpsY"]))
                tm = datetime.strptime(it["dataTm"], "%Y%m%d%H%M%S").replace(tzinfo=KST)
                m = base + float(it["sectDist"] or 0) * 1000
                out.append(
                    Obs(
                        it["vehId"],
                        it["plainNo"],
                        tm,
                        m,
                        rp.distance_m(x, y),
                        int(it["sectOrd"]),
                        it["stopFlag"] == "1",
                        it["lastStnId"],
                    )
                )
    return sorted(out, key=lambda o: (o.veh, o.tm))


def passes(obs: list[Obs], lo: float, hi: float) -> list[list[Obs]]:
    """구간 앞 관측 → (구간 안 관측들) → 구간 뒤 관측, 20분 안."""
    by_veh: dict[str, list[Obs]] = defaultdict(list)
    for o in obs:
        by_veh[o.veh].append(o)
    out = []
    for os_ in by_veh.values():
        i = 0
        while i < len(os_):
            if os_[i].m >= lo:
                i += 1
                continue
            j = i + 1
            while j < len(os_) and os_[j].m < lo:
                i, j = j, j + 1
            k = j
            while k < len(os_) and lo <= os_[k].m <= hi:
                k += 1
            if k < len(os_) and os_[k].m > hi and os_[k].tm - os_[i].tm <= WITHIN:
                out.append(os_[i : k + 1])
                i = k
            else:
                i = j
    return sorted(out, key=lambda p: p[0].tm)


def kmh(a: Obs, b: Obs) -> float:
    s = (b.tm - a.tm).total_seconds()
    return (b.m - a.m) / s * 3.6 if s > 0 else 0.0


def med(ps: list[list[Obs]]) -> str:
    """통과들의 속도 가운데값 (앞 관측 → 뒤 관측), 없으면 -."""
    return f"{statistics.median([kmh(p[0], p[-1]) for p in ps]):.1f}" if ps else "-"


def row(cells: list[object]) -> None:
    """markdown 표 한 줄."""
    print("| " + " | ".join(str(c) for c in cells) + " |")


def main(root: Path) -> None:
    cs = controls(root)
    routes = {r for _, rs, _ in CONTROLS for r in rs}
    stops = stops_of(root, routes)
    row(["통제", "창", "횡단보도", "부른 노선"])
    row(["---"] * 4)
    for prefix, rs, _ in CONTROLS:
        win, pts = cs[prefix]
        row([prefix, f"{win['start'][11:16]}~{win['end'][11:16]}", len(pts), " · ".join(rs)])
    print()
    head = ["노선", "관측", "차량", "경로까지 가운데", "최대", "60 m 밖", "2회 연속"]
    row(head)
    row(["---"] * len(head))
    cache = {}
    for route in sorted(routes):
        rp = RoutePath.load(root / "raw" / "bus_routes" / DAY / f"path_{route}.json")
        sm = stop_measures(rp, stops[route])
        obs = observations(root, route, rp, sm)
        cache[route] = (rp, sm, obs)
        ds = sorted(o.d for o in obs)
        twice = sum(
            a.veh == b.veh and min(a.d, b.d) > OFF_ROUTE_M for a, b in itertools.pairwise(obs)
        )
        far = sum(d > OFF_ROUTE_M for d in ds)
        vehicles = len({o.veh for o in obs})
        mid, top_d = f"{statistics.median(ds):.2f} m", f"{ds[-1]:.1f} m"
        row([route, f"{len(obs):,}", vehicles, mid, top_d, far, twice])
    print()
    head = ["통제", "창", "노선", "구간(노선 위 m)", "구간 정류소", "통과(창 안·뒤)"]
    head += ["속도 가운데 km/h(창 안·뒤)", "정차 관측 있는 통과", "관측 사이 최고 km/h", "60 m 밖"]
    row(head)
    row(["---"] * len(head))
    total = inside_total = 0
    for prefix, rs, _ in CONTROLS:
        win, pts = cs[prefix]
        w0, w1 = datetime.fromisoformat(win["start"]), datetime.fromisoformat(win["end"])
        for route in rs:
            rp, sm, obs = cache[route]
            name = {seq: nm for seq, _, nm, *_ in stops[route]}
            for a, b in rp.passes({k: to_5179(*v) for k, v in pts.items()}):
                lo, hi = a - MARGIN_M, b + MARGIN_M
                ps = passes(obs, lo, hi)
                inside = [p for p in ps if w0 <= p[0].tm <= w1]
                after = [p for p in ps if p[0].tm > w1]
                total, inside_total = total + len(ps), inside_total + len(inside)
                stopped = sum(any(o.stop for o in p) for p in ps)
                pairs = (kmh(x, y) for p in ps for x, y in itertools.pairwise(p))
                top = max(pairs, default=0.0)
                far = sum(o.d > OFF_ROUTE_M for p in ps for o in p)
                sec_stops = ", ".join(name[s] for s in sorted(sm) if lo <= sm[s] <= hi) or "-"
                window = f"{win['start'][11:16]}~{win['end'][11:16]}"
                span = f"{round(lo):,}~{round(hi):,}"
                count = f"{len(ps)} ({len(inside)}·{len(after)})"
                speed = f"{med(inside)}·{med(after)}"
                row(
                    [
                        prefix,
                        window,
                        route,
                        span,
                        sec_stops,
                        count,
                        speed,
                        stopped,
                        f"{top:.1f}",
                        far,
                    ]
                )
    print(f"\n통과 합계 {total} — 통제 시간 안 {inside_total}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data"))
