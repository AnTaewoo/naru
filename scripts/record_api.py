"""실제 API 응답 기록 — `make record API=incident|links|rtd|bus|kakao|all` (ROADMAP T0.7).

호출 1회의 원문을 그대로 `data/recorded/<api>/<ts>_<이름>.json` 에 둔다 (real-data-testing §3:
api, endpoint(키 가림), params(키 없음), called_at, status, raw). 손으로 고치지 않는다.

  incident  서울 열린데이터광장 TOPIS 돌발 — AccMainCode(돌발 유형 코드) · AccSubCode(세부 유형) ·
            AccInfo(실시간 돌발: acc_type, link_id, grs80tm_x/y[EPSG:5181], acc_info). xml만. 3회
  links     최근 AccInfo 기록에서 유형이 집회및행사·공사·기타인 돌발의 link_id를 골라
            LinkInfo(도로명·노드명) + LinkVerInfo(vertex TM 좌표). 링크당 2회, --limit 로 상한
  rtd       서울 실시간 도시데이터 citydata (json) — 광화문·덕수궁 1회
  bus       서울 버스위치정보 getBusPosByRtid (ws.bus.go.kr, data.go.kr 키) 1회
  kakao     카카오 로컬 키워드 검색 — 숭례문·덕수궁 1회씩. 리졸버 재생용으로
            data/recorded/kakao/keyword/<sha1(검색어)>.json 에 둔다 (real-data-testing §4.3)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("record_api")
KST = timezone(timedelta(hours=9))
SEOUL_API = "http://openapi.seoul.go.kr:8088"
BUS_API = "http://ws.bus.go.kr/api/rest/buspos/getBusPosByRtid"
KAKAO_API = "https://dapi.kakao.com/v2/local/search/keyword.json"
UA = {"User-Agent": "naru-record/0.5"}

INCIDENT_SERVICES = (("AccMainCode", 100), ("AccSubCode", 300), ("AccInfo", 1000))
LINK_TYPES = ("집회및행사", "공사", "기타")  # 태우 지시 — confirmed 신호로 쓸 돌발 유형
RTD_AREA = "광화문·덕수궁"  # citydata AREA_NM (sample 응답에서 확인: AREA_CD POI009)
BUS_ROUTE_ID = "100100118"  # data.go.kr 활용가이드 예시 노선 (응답 headerCd=0 이어야 유효)
KAKAO_QUERIES = ("숭례문", "덕수궁", "교보빌딩")  # 교보빌딩은 T3.1 라우터 테스트 출발점
SECRETS: list[str] = []  # 응답 본문에 키가 섞여 와도(카카오 401이 그랬다) 기록에는 남기지 않는다


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    seoul_opendata_key: str = ""
    data_go_kr_key: str = ""
    kakao_rest_key: str = ""


def need(value: str, name: str) -> str:
    if not value:
        raise SystemExit(f"{name} 없음 — .env 확인")
    return value


def _mask(text: str) -> str:
    for secret in SECRETS:
        text = text.replace(secret, "<키>")
    return text


def write_record(
    path: Path,
    api: str,
    endpoint: str,
    params: dict[str, object],
    r: httpx.Response,
    called_at: datetime,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "api": api,
        "endpoint": endpoint,
        "params": params,
        "called_at": called_at.isoformat(timespec="seconds"),
        "status": r.status_code,
        "raw": _mask(r.text),
    }
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", "utf-8")
    log.info("%s → %s (HTTP %d, %d bytes)", api, path.name, r.status_code, len(r.content))
    return path


def seoul_call(
    client: httpx.Client, key: str, fmt: str, service: str, start: int, end: int, *extra: str
) -> tuple[str, httpx.Response, datetime]:
    parts = [SEOUL_API, key, fmt, service, str(start), str(end), *(quote(e) for e in extra)]
    masked = "/".join([SEOUL_API, "<키>", fmt, service, str(start), str(end), *extra]) + "/"
    called_at = datetime.now(KST)
    r = client.get("/".join(parts) + "/")
    return masked, r, called_at


def seoul_rows(raw: str, service: str) -> list[dict[str, str]]:
    root = ET.fromstring(raw)
    if root.tag != service:
        raise SystemExit(
            f"{service}: {root.findtext('RESULT/CODE')} {root.findtext('RESULT/MESSAGE')}"
        )
    return [{c.tag: (c.text or "") for c in row} for row in root.findall("row")]


def record_incident(client: httpx.Client, settings: Settings, out: Path) -> None:
    key = need(settings.seoul_opendata_key, "SEOUL_OPENDATA_KEY")
    stamp = datetime.now(KST).strftime("%Y%m%dT%H%M%S")
    for service, end in INCIDENT_SERVICES:
        masked, r, called_at = seoul_call(client, key, "xml", service, 1, end)
        params = {"service": service, "type": "xml", "start": 1, "end": end}
        write_record(
            out / "incident" / f"{stamp}_{service}.json", "incident", masked, params, r, called_at
        )
        rows = seoul_rows(r.text, service)
        log.info("  %s: %d행", service, len(rows))


def latest(out: Path, api: str, name: str) -> Path:
    files = sorted((out / api).glob(f"*_{name}*.json"))
    if not files:
        raise SystemExit(f"{api}/{name} 기록 없음 — make record API=incident 먼저")
    return files[-1]


def record_links(client: httpx.Client, settings: Settings, out: Path, limit: int) -> None:
    key = need(settings.seoul_opendata_key, "SEOUL_OPENDATA_KEY")
    codes = json.loads(latest(out, "incident", "AccMainCode").read_text("utf-8"))
    names = {row["acc_type"]: row["acc_type_nm"] for row in seoul_rows(codes["raw"], "AccMainCode")}
    wanted = {code for code, name in names.items() if name in LINK_TYPES}
    acc = json.loads(latest(out, "incident", "AccInfo").read_text("utf-8"))
    rows = seoul_rows(acc["raw"], "AccInfo")
    # 집회및행사 → 공사 → 기타 순, 같은 링크는 한 번만
    order = {name: i for i, name in enumerate(LINK_TYPES)}
    rows = sorted(
        (r for r in rows if r["acc_type"] in wanted), key=lambda r: order[names[r["acc_type"]]]
    )
    link_ids: list[str] = []
    for r in rows:
        if r["link_id"] and r["link_id"] not in link_ids:
            link_ids.append(r["link_id"])
    link_ids = link_ids[:limit]
    log.info(
        "돌발 유형 %s 링크 %d개 중 %d개 기록", {names[c] for c in wanted}, len(rows), len(link_ids)
    )
    stamp = datetime.now(KST).strftime("%Y%m%dT%H%M%S")
    for link_id in link_ids:
        for service in ("LinkInfo", "LinkVerInfo"):
            masked, r, called_at = seoul_call(client, key, "xml", service, 1, 100, link_id)
            params = {"service": service, "type": "xml", "start": 1, "end": 100, "LINK_ID": link_id}
            write_record(
                out / "links" / f"{stamp}_{service}_{link_id}.json",
                "links",
                masked,
                params,
                r,
                called_at,
            )


def record_rtd(client: httpx.Client, settings: Settings, out: Path) -> None:
    key = need(settings.seoul_opendata_key, "SEOUL_OPENDATA_KEY")
    masked, r, called_at = seoul_call(client, key, "json", "citydata", 1, 5, RTD_AREA)
    params = {"service": "citydata", "type": "json", "start": 1, "end": 5, "AREA_NM": RTD_AREA}
    stamp = called_at.strftime("%Y%m%dT%H%M%S")
    write_record(out / "rtd" / f"{stamp}_citydata.json", "rtd", masked, params, r, called_at)


def record_bus(client: httpx.Client, settings: Settings, out: Path) -> None:
    key = unquote(
        need(settings.data_go_kr_key, "DATA_GO_KR_KEY")
    )  # 인코딩 키면 풀어서 httpx가 다시 인코딩
    params = {"busRouteId": BUS_ROUTE_ID, "resultType": "json"}
    called_at = datetime.now(KST)
    r = client.get(BUS_API, params={"serviceKey": key, **params})
    stamp = called_at.strftime("%Y%m%dT%H%M%S")
    write_record(
        out / "bus" / f"{stamp}_getBusPosByRtid.json",
        "bus",
        f"{BUS_API}?serviceKey=<키>",
        params,
        r,
        called_at,
    )


def record_kakao(client: httpx.Client, settings: Settings, out: Path) -> None:
    key = need(settings.kakao_rest_key, "KAKAO_REST_KEY")
    for query in KAKAO_QUERIES:
        called_at = datetime.now(KST)
        r = client.get(
            KAKAO_API, params={"query": query}, headers={"Authorization": f"KakaoAK {key}", **UA}
        )
        name = hashlib.sha1(query.encode("utf-8")).hexdigest()
        write_record(
            out / "kakao" / "keyword" / f"{name}.json",
            "kakao",
            KAKAO_API,
            {"query": query},
            r,
            called_at,
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실제 API 응답 기록 (T0.7)")
    ap.add_argument(
        "--api", required=True, choices=["incident", "links", "rtd", "bus", "kakao", "all"]
    )
    ap.add_argument("--recorded", type=Path, default=Path("data/recorded"))
    ap.add_argument("--limit", type=int, default=4, help="links: 기록할 링크 수 (링크당 2회 호출)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # URL에 키가 있다
    settings = Settings()
    SECRETS.extend(
        v
        for v in (
            settings.seoul_opendata_key,
            settings.data_go_kr_key,
            unquote(settings.data_go_kr_key),
            settings.kakao_rest_key,
        )
        if v
    )
    with httpx.Client(timeout=60.0, headers=UA) as client:
        if args.api in ("incident", "all"):
            record_incident(client, settings, args.recorded)
        if args.api in ("links", "all"):
            record_links(client, settings, args.recorded, args.limit)
        if args.api in ("rtd", "all"):
            record_rtd(client, settings, args.recorded)
        if args.api in ("bus", "all"):
            record_bus(client, settings, args.recorded)
        if args.api in ("kakao", "all"):
            record_kakao(client, settings, args.recorded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
