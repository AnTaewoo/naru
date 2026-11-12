"""표준노드링크(국토부) → 서울 추출 CLI — `make fetch SRC=nodelink` (ROADMAP T0.3).

zip은 공공데이터포털에서 로그인 뒤 수동으로 받아 `data/raw/nodelink_<YYYYMMDD>/`에 푼다
(MOCT_NODE.*, MOCT_LINK.*, MULTILINK.dbf, TURNINFO.dbf, 내역서.csv). 원본은 건드리지 않는다.
이 스크립트는 그 폴더에서 서울(ID 앞 2자리 10·11·12)만 뽑아
`data/raw/nodelink_seoul_<YYYYMMDD>/node.gpkg`·`link.gpkg`로 저장하고
`_meta.json`에 원본 sha256·건수·범위·좌표계를 남긴다.

ID 앞 4자리 = 서울 자치구(행정코드 순): 1000 종로구, 1010 중구, …, 1180 영등포구.
16xx = 인천, 2xxx = 경기 (2026-11-07 노드명·중심 좌표로 확인).
좌표계는 .prj 그대로(ITRF2000 중부원점 TM, EPSG:5186과 수치 동일). BE는 5179로 변환해 쓴다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import geopandas as gpd
import pyogrio

log = logging.getLogger("fetch_nodelink")
KST = timezone(timedelta(hours=9))
ENCODING = "cp949"  # dbf 한글
SEOUL_PREFIXES = ("10", "11", "12")  # NODE_ID·LINK_ID 앞 2자리
SEOUL_BBOX = (126.76, 37.41, 127.19, 37.72)  # WGS84. 추출 결과는 전부 이 안이어야 한다
DISTRICTS = {"1000": "종로구", "1010": "중구", "1180": "영등포구"}  # 데모 범위 (테스트가 확인)
SOURCE_FILES = (
    "MOCT_NODE.shp",
    "MOCT_NODE.dbf",
    "MOCT_NODE.shx",
    "MOCT_NODE.prj",
    "MOCT_LINK.shp",
    "MOCT_LINK.dbf",
    "MOCT_LINK.shx",
    "MOCT_LINK.prj",
    "MULTILINK.dbf",
    "TURNINFO.dbf",
    "내역서.csv",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def latest_source(raw: Path) -> Path:
    dirs = sorted(p for p in raw.glob("nodelink_*") if p.is_dir() and "_seoul" not in p.name)
    if not dirs:
        raise SystemExit("원본 없음: data/raw/nodelink_<YYYYMMDD>/ 에 zip을 풀어 둔다")
    return dirs[-1]


def read_seoul(path: Path, id_col: str) -> gpd.GeoDataFrame:
    """OGR SQL where로 서울 ID만 읽는다 (전국 156만 링크를 메모리에 다 올리지 않는다)."""
    where = " OR ".join(f"{id_col} LIKE '{p}%'" for p in SEOUL_PREFIXES)
    gdf: gpd.GeoDataFrame = pyogrio.read_dataframe(path, where=where, encoding=ENCODING)
    return gdf


def wgs84_bounds(gdf: gpd.GeoDataFrame, name: str) -> list[float]:
    b = [round(float(v), 6) for v in gdf.to_crs(4326).total_bounds]
    inside = (
        b[0] > SEOUL_BBOX[0]
        and b[1] > SEOUL_BBOX[1]
        and b[2] < SEOUL_BBOX[2]
        and b[3] < SEOUL_BBOX[3]
    )
    if not inside:
        raise SystemExit(f"{name}: 서울 범위 밖 — {b}. ID 접두사 규칙이 바뀌었는지 확인")
    return b


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="표준노드링크 서울 추출 (T0.3)")
    ap.add_argument(
        "--src", type=Path, default=None, help="풀어 둔 원본 폴더 (기본: 최신 nodelink_<date>)"
    )
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    src = args.src or latest_source(args.raw)
    date = src.name.removeprefix("nodelink_")
    out = args.raw / f"nodelink_seoul_{date}"
    out.mkdir(parents=True, exist_ok=True)

    nodes = read_seoul(src / "MOCT_NODE.shp", "NODE_ID")
    links = read_seoul(src / "MOCT_LINK.shp", "LINK_ID")
    log.info("서울 추출: 노드 %d, 링크 %d (원본 %s)", len(nodes), len(links), src)
    node_bounds = wgs84_bounds(nodes, "node")
    link_bounds = wgs84_bounds(links, "link")
    node_ids = set(nodes["NODE_ID"])
    dangling = ~links["F_NODE"].isin(node_ids) | ~links["T_NODE"].isin(node_ids)

    nodes.to_file(out / "node.gpkg", driver="GPKG", layer="node")
    links.to_file(out / "link.gpkg", driver="GPKG", layer="link")

    districts = {
        code: {
            "name": name,
            "nodes": int(nodes["NODE_ID"].str.startswith(code).sum()),
            "links": int(links["LINK_ID"].str.startswith(code).sum()),
        }
        for code, name in DISTRICTS.items()
    }
    note = src / "내역서.csv"
    meta = {
        "fetched_at": datetime.now(KST).isoformat(timespec="seconds"),
        "source_dir": str(src),
        "source_note": note.read_text(encoding=ENCODING) if note.exists() else None,
        "source_sha256": {f: sha256(src / f) for f in SOURCE_FILES if (src / f).exists()},
        "filter": {"id_prefix": list(SEOUL_PREFIXES), "encoding": ENCODING},
        "crs_wkt": nodes.crs.to_wkt() if nodes.crs is not None else None,
        "nodes": len(nodes),
        "links": len(links),
        "dangling_links": int(dangling.sum()),  # F/T 노드가 서울 밖(경기·인천)인 링크
        "bounds_wgs84": {"node": node_bounds, "link": link_bounds},
        "districts": districts,
        "files": {
            n: {"bytes": (out / n).stat().st_size, "sha256": sha256(out / n)}
            for n in ("node.gpkg", "link.gpkg")
        },
    }
    (out / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", "utf-8")
    log.info("완료: %s (종로 %s / 중구 %s / 영등포 %s)", out, *(districts[c] for c in DISTRICTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
