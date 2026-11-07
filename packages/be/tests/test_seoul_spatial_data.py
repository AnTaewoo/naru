"""T0.2 — 서울 열린데이터광장 공간 데이터가 받아진 그대로 열리는지 (실데이터).

기대값은 전부 2026-11-07에 파일을 열어 확인한 값. 옆 주석이 확인 방법이다.
"""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import Transformer

# WGS84 범위. 벗어나면 좌표계가 틀린 것 (API 좌표는 WGS84, 횡단보도 xlsx는 EPSG:5186)
CENTRAL = (126.90, 37.45, 127.10, 37.70)  # 종로구·중구만 받은 데이터
SEOUL = (126.76, 37.41, 127.19, 37.72)  # 25개 자치구 전체 데이터

# 서울 전체를 한 번에 주는 서비스 (SGG_NM 필터 없음)
SERVICES_CITYWIDE = (
    "tbTraficUndpass",
    "tbTraficBrdge",
    "tbTraficElvtr",
    "tbTraficEntrcLft",
    "tbTraficCrsng",
)


def _load_pages(service_dir: Path) -> tuple[list[dict[str, object]], int]:
    """<start>-<end>.json 페이지 전부 → (row 목록, 첫 페이지의 list_total_count)."""
    pages = sorted(service_dir.glob("*.json"))
    assert pages, f"페이지 없음: {service_dir}"
    rows: list[dict[str, object]] = []
    total = -1
    for p in pages:
        body = json.loads(p.read_bytes())
        payload = next(iter(body.values()))
        assert payload["RESULT"]["CODE"] == "INFO-000", (p, payload["RESULT"])
        if total < 0:
            total = int(payload["list_total_count"])
        rows.extend(payload["row"])
    return rows, total


def _to_gdf(rows: list[dict[str, object]]) -> gpd.GeoDataFrame:
    df = pd.DataFrame(rows)
    wkt = df["NODE_WKT"]
    if "LNKG_WKT" in df.columns:  # 엘리베이터·리프트는 NODE만 와서 LNKG_* 컬럼이 없다
        wkt = wkt.where(df["NODE_TYPE"] == "NODE", df["LNKG_WKT"])
    return gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(wkt), crs="EPSG:4326")


def _assert_within(gdf: gpd.GeoDataFrame, bbox: tuple[float, float, float, float]) -> None:
    minx, miny, maxx, maxy = gdf.total_bounds
    assert minx > bbox[0] and maxx < bbox[2], (minx, maxx)
    assert miny > bbox[1] and maxy < bbox[3], (miny, maxy)


def test_walk_net_jongno_junggu(seoul_spatial_dir: Path) -> None:
    for sgg_dir, sgg_nm, total_expected in (
        # list_total_count: API 첫 페이지 (2026-11-07 확인) — 종로구 19,266 / 중구 13,622
        ("TbTraficWlkNet_jongno", "종로구", 19266),
        ("TbTraficWlkNet_junggu", "중구", 13622),
    ):
        rows, total = _load_pages(seoul_spatial_dir / sgg_dir)
        assert total == total_expected
        assert len(rows) == total
        gdf = _to_gdf(rows)
        assert set(gdf["SGG_NM"]) == {sgg_nm}
        assert set(gdf["NODE_TYPE"]) == {"NODE", "LINK"}
        assert gdf.geometry.notna().all()
        _assert_within(gdf, CENTRAL)
        links = gdf[gdf["NODE_TYPE"] == "LINK"]
        # 횡단보도 링크(CRSWK == "1"): 종로구 963, 중구 1,056 (페이지 row를 세어 확인)
        assert (links["CRSWK"] == "1").sum() > 100  # T1.1 기준
        # 링크 유형코드는 4자리 (OA-21208_codes.xlsx 링크유형코드 시트)
        assert set(links["LNKG_TYPE_CD"].str.len()) == {4}


def test_citywide_overlays(seoul_spatial_dir: Path) -> None:
    for service in SERVICES_CITYWIDE:
        rows, total = _load_pages(seoul_spatial_dir / service)
        assert total > 0 and len(rows) == total, service
        gdf = _to_gdf(rows)
        assert gdf.geometry.notna().all(), service
        _assert_within(gdf, SEOUL)
        assert (gdf["SGG_NM"] == "종로구").any(), service


def test_crosswalk_xlsx_columns_and_crs(seoul_spatial_dir: Path) -> None:
    df = pd.read_excel(seoul_spatial_dir / "OA-23081.xlsx")
    # 헤더 1행 (openpyxl로 열어 확인, 2026-11-07)
    assert list(df.columns) == [
        "연번",
        "자치구",
        "횡단보도관리번호",
        "교차로관리번호",
        "횡단보도종류",
        "보행등유무",
        "교차로명",
        "X좌표",
        "Y좌표",
    ]
    assert len(df) == 21776  # 데이터 행 수 (헤더 제외)
    assert df["교차로명"].notna().all()
    by_gu = df["자치구"].value_counts()
    assert by_gu["종로구"] == 590 and by_gu["중구"] == 621
    # 교차로명 '세종대로사거리' 8행, 전부 종로구, 교차로관리번호 535
    sejong = df[df["교차로명"] == "세종대로사거리"]
    assert len(sejong) == 8 and set(sejong["자치구"]) == {"종로구"}
    assert set(sejong["교차로관리번호"]) == {535}
    # X·Y는 WGS84가 아니라 EPSG:5186(중부원점 TM). 5186→4326이면 세종대로사거리가 광화문 앞에 온다
    to_wgs = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
    lng, lat = to_wgs.transform(sejong["X좌표"].to_numpy(), sejong["Y좌표"].to_numpy())
    assert lng.min() > 126.975 and lng.max() < 126.978, (lng.min(), lng.max())
    assert lat.min() > 37.569 and lat.max() < 37.571, (lat.min(), lat.max())


def test_walk_net_type_codes(seoul_spatial_dir: Path) -> None:
    path = seoul_spatial_dir / "OA-21208_codes.xlsx"
    sheets = pd.read_excel(path, sheet_name=None, header=None)
    assert list(sheets) == ["링크유형코드", "노드유형코드"]
    link_codes = sheets["링크유형코드"].astype(str)
    assert ((link_codes[1] == "1000") & (link_codes[3] == "보행자")).any()
    node_codes = sheets["노드유형코드"].astype(str)
    assert (node_codes[1] == "3").any() and node_codes[3].str.contains("지하보도 출입구").any()
