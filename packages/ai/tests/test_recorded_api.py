"""T0.7 — 실제 API 응답 기록이 열리고, 열어서 확인한 필드가 있는지 (실데이터, 재생만).

기록은 2026-11-07 `make record API=incident|links|rtd` 로 만든 파일 그대로.
기대값은 그 파일을 열어 확인한 값.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pyproj import Transformer

SEOUL = (126.76, 37.41, 127.19, 37.72)  # WGS84
TO_WGS = Transformer.from_crs(
    "EPSG:5181", "EPSG:4326", always_xy=True
)  # TOPIS grs80tm_* (봉은교 vertex로 확인)


def _rows(path: Path, service: str) -> list[dict[str, str]]:
    rec = json.loads(path.read_text("utf-8"))
    assert rec["status"] == 200 and rec["api"] and rec["called_at"].endswith("+09:00")
    assert "<키>" in rec["endpoint"] or "serviceKey=<키>" in rec["endpoint"]  # 키는 기록하지 않는다
    root = ET.fromstring(rec["raw"])
    assert root.tag == service and root.findtext("RESULT/CODE") == "INFO-000"
    return [{c.tag: (c.text or "") for c in row} for row in root.findall("row")]


def _in_seoul(x: float, y: float) -> bool:
    lng, lat = TO_WGS.transform(x, y)
    return SEOUL[0] < lng < SEOUL[2] and SEOUL[1] < lat < SEOUL[3]


def test_incident_code_tables(recorded_dir: Path) -> None:
    main = _rows(recorded_dir / "incident" / "20261107T154053_AccMainCode.json", "AccMainCode")
    names = {r["acc_type"]: r["acc_type_nm"] for r in main}
    assert len(names) == 13  # A01~A13 (기록 파일)
    assert names["A10"] == "집회및행사" and names["A04"] == "공사" and names["A11"] == "기타"
    sub = _rows(recorded_dir / "incident" / "20261107T154053_AccSubCode.json", "AccSubCode")
    dnames = {r["acc_dtype"]: r["acc_dtype_nm"] for r in sub}
    assert len(dnames) == 43 and dnames["10B02"] == "집회" and dnames["10B03"] == "행사"


def test_incident_rows_have_link_and_tm_coords(recorded_dir: Path) -> None:
    acc = _rows(recorded_dir / "incident" / "20261107T154053_AccInfo.json", "AccInfo")
    assert len(acc) == 53  # 2026-11-07 15:40 기준 진행 중 돌발
    fields = {
        "acc_id",
        "occr_date",
        "occr_time",
        "exp_clr_date",
        "exp_clr_time",
        "acc_type",
        "acc_dtype",
    }
    fields |= {"link_id", "grs80tm_x", "grs80tm_y", "acc_info"}
    assert all(fields <= set(r) for r in acc)
    assert all(_in_seoul(float(r["grs80tm_x"]), float(r["grs80tm_y"])) for r in acc)
    assembly = [r for r in acc if r["acc_type"] == "A10"]
    assert len(assembly) == 15  # 집회및행사 (공사 27, 기타 6, 교통사고 4, 차량고장 1)
    # 세종대로(시청역 → 숭례문) 집회 무대 전차로 통제 — link 1010005900, 07:00~16:00
    sejong = next(r for r in assembly if r["acc_id"] == "1108984")
    assert sejong["link_id"] == "1010005900" and sejong["occr_date"] == "20261107"
    assert "세종대로" in sejong["acc_info"] and "전차로 통제" in sejong["acc_info"]


def test_link_info_and_vertices(recorded_dir: Path) -> None:
    links = recorded_dir / "links"
    # LinkInfo 1000003700: 청계천로 청계광장→무교동사거리 199 m
    # (표준노드링크 1000003700도 청계천로 188 m, 양 끝 좌표가 같다)
    info = _rows(links / "20261107T154055_LinkInfo_1000003700.json", "LinkInfo")
    assert len(info) == 1 and info[0]["road_name"] == "청계천로"
    assert info[0]["st_node_nm"] == "청계광장" and info[0]["ed_node_nm"] == "무교동사거리"
    assert info[0]["map_dist"] == "199"
    ver = _rows(links / "20261107T154055_LinkVerInfo_1000003700.json", "LinkVerInfo")
    assert [v["ver_seq"] for v in ver] == ["1", "2", "3"]
    first = TO_WGS.transform(float(ver[0]["grs80tm_x"]), float(ver[0]["grs80tm_y"]))
    last = TO_WGS.transform(float(ver[-1]["grs80tm_x"]), float(ver[-1]["grs80tm_y"]))
    # 표준노드링크 1000003700 시작 (126.97711, 37.56903) · 끝 (126.97923, 37.56898) 과 10 m 안
    assert abs(first[0] - 126.97711) < 0.0002 and abs(first[1] - 37.56903) < 0.0001
    assert abs(last[0] - 126.97923) < 0.0002 and abs(last[1] - 37.56898) < 0.0001
    for p in links.glob("*_LinkVerInfo_*.json"):
        rows = _rows(p, "LinkVerInfo")
        assert rows and all(
            _in_seoul(float(v["grs80tm_x"]), float(v["grs80tm_y"])) for v in rows
        ), p.name


def test_citydata_gwanghwamun(recorded_dir: Path) -> None:
    rec = json.loads((recorded_dir / "rtd" / "20261107T154125_citydata.json").read_text("utf-8"))
    assert rec["status"] == 200 and rec["params"]["AREA_NM"] == "광화문·덕수궁"
    body = json.loads(rec["raw"])
    assert body["RESULT"]["RESULT.CODE"] == "INFO-000"
    city = body["CITYDATA"]
    assert city["AREA_NM"] == "광화문·덕수궁" and city["AREA_CD"] == "POI009"
    live = city["LIVE_PPLTN_STTS"][0]
    assert live["AREA_CONGEST_LVL"] in ("여유", "보통", "약간 붐빔", "붐빔")
    assert live["PPLTN_TIME"].startswith("2026-11-07 ")
    assert int(live["AREA_PPLTN_MIN"]) <= int(live["AREA_PPLTN_MAX"])


def test_kakao_keyword_records(recorded_dir: Path) -> None:
    # 리졸버 재생 규칙: kakao/keyword/<sha1(검색어)>.json (real-data-testing §4.3)
    import hashlib

    expected = {
        # 검색어: (1순위 place_name, id, x, y) — 기록 파일 documents[0]
        "숭례문": ("숭례문", "7813430", "126.975313124237", "37.5600030088843"),
        "덕수궁": ("덕수궁", "10305191", "126.974894754989", "37.5655638710672"),
    }
    for query, (name, doc_id, x, y) in expected.items():
        path = (
            recorded_dir / "kakao" / "keyword" / f"{hashlib.sha1(query.encode()).hexdigest()}.json"
        )
        rec = json.loads(path.read_text("utf-8"))
        assert rec["status"] == 200 and rec["params"] == {"query": query}
        assert rec["endpoint"] == "https://dapi.kakao.com/v2/local/search/keyword.json"
        body = json.loads(rec["raw"])
        assert body["meta"]["total_count"] > 0
        top = body["documents"][0]
        assert {"id", "place_name", "x", "y", "address_name", "road_address_name"} <= set(top)
        assert (top["place_name"], top["id"], top["x"], top["y"]) == (name, doc_id, x, y)
        assert SEOUL[0] < float(top["x"]) < SEOUL[2] and SEOUL[1] < float(top["y"]) < SEOUL[3]


def test_bus_positions_record(recorded_dir: Path) -> None:
    # 2026-11-07 15:56 기록, 노선 100100118 (활용가이드 예시)
    # msgHeader.itemCount는 0이어도 itemList가 있다
    rec = json.loads(
        (recorded_dir / "bus" / "20261107T155630_getBusPosByRtid.json").read_text("utf-8")
    )
    assert rec["status"] == 200 and rec["params"] == {
        "busRouteId": "100100118",
        "resultType": "json",
    }
    assert rec["endpoint"].endswith("getBusPosByRtid?serviceKey=<키>")
    body = json.loads(rec["raw"])
    assert body["msgHeader"]["headerCd"] == "0"  # 정상 (오류코드는 bus 메모·활용가이드)
    items = body["msgBody"]["itemList"]
    assert len(items) == 12
    fields = {"vehId", "plainNo", "dataTm", "gpsX", "gpsY", "posX", "posY", "tmX", "tmY"}
    fields |= {
        "sectOrd",
        "sectionId",
        "sectDist",
        "stopFlag",
        "lastStnId",
        "nextStId",
        "isrunyn",
        "congetion",
    }
    assert all(fields <= set(it) for it in items)
    first = items[0]
    assert first["vehId"] == "111033056" and first["dataTm"] == "20261107155417"
    assert all(it["dataTm"].startswith("20261107") for it in items)
    assert all(
        SEOUL[0] < float(it["gpsX"]) < SEOUL[2] and SEOUL[1] < float(it["gpsY"]) < SEOUL[3]
        for it in items
    )
