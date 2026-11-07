"""서울 열린데이터광장 공간 데이터 수집 CLI — `make fetch SRC=seoul_spatial` (ROADMAP T0.2).

산출: data/raw/seoul_spatial_<YYYYMMDD>/
  TbTraficWlkNet_jongno/, TbTraficWlkNet_junggu/  도보 네트워크 노드·링크 (OA-21208, SGG_NM 필터)
  tbTraficUndpass/  지하철역 연계 지하도 (OA-21213)
  tbTraficBrdge/    육교 (OA-21210)
  tbTraficElvtr/    지하철역 엘리베이터 (OA-21212)
  tbTraficEntrcLft/ 지하철 출입구 리프트 (OA-21211)
  tbTraficCrsng/    대로변 횡단보도 (OA-21209)
  OA-23081.xlsx     교차로 및 횡단보도 시설·위치정보 (파일. X·Y는 EPSG:5186)
  OA-21208_codes.xlsx  도보네트워크 링크·노드 유형코드표
  _meta.json        호출 기록 (서비스·건수·sha256). 인증키는 저장하지 않는다

API 응답은 받은 바이트 그대로 <start>-<end>.json 으로 둔다. 이미 있는 페이지는 다시 받지 않는다.
한 번에 최대 1,000건 (열린데이터광장 이용안내). 2026-11-07 기준 전체 약 80회 호출.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("fetch_seoul_spatial")

API_BASE = "http://openapi.seoul.go.kr:8088"
FILE_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
PAGE = 1000  # 한 번에 최대 1,000건
RETRIES = 3
KST = timezone(timedelta(hours=9))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    seoul_opendata_key: str = ""


@dataclass(frozen=True)
class ApiDataset:
    service: str
    dir_name: str
    dataset_id: str
    params: tuple[str, ...] = ()  # START/END 뒤에 붙는 선택 인자 (TbTraficWlkNet: SGG_NM)


API_DATASETS = (
    ApiDataset("TbTraficWlkNet", "TbTraficWlkNet_jongno", "OA-21208", ("종로구",)),
    ApiDataset("TbTraficWlkNet", "TbTraficWlkNet_junggu", "OA-21208", ("중구",)),
    # SGG_NM 필터 페이지는 서로 겹쳐 유일 행이 64~74%뿐 (2026-11-07 확인).
    # 전체 조회는 안 겹친다 → 서울 전체를 받아 로컬에서 거른다
    ApiDataset("TbTraficWlkNet", "TbTraficWlkNet_seoul", "OA-21208"),
    ApiDataset("tbTraficUndpass", "tbTraficUndpass", "OA-21213"),
    ApiDataset("tbTraficBrdge", "tbTraficBrdge", "OA-21210"),
    ApiDataset("tbTraficElvtr", "tbTraficElvtr", "OA-21212"),
    ApiDataset("tbTraficEntrcLft", "tbTraficEntrcLft", "OA-21211"),
    ApiDataset("tbTraficCrsng", "tbTraficCrsng", "OA-21209"),
)

# 파일 다운로드 폼 = datasetView.do의 frmFile. infSeq는 fileView.do?infId=…에서 확인 (2026-11-07)
FILES = (
    ("OA-23081.xlsx", {"infId": "OA-23081", "seq": "1", "infSeq": "1"}),
    ("OA-21208_codes.xlsx", {"infId": "OA-21208", "seq": "1", "infSeq": "3"}),
)


class FetchError(RuntimeError):
    """요청 실패. 인증키가 URL에 있으므로 httpx 예외 메시지를 그대로 올리지 않는다."""


def dataset_url(dataset_id: str) -> str:
    return f"https://data.seoul.go.kr/dataList/{dataset_id}/S/1/datasetView.do"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get(client: httpx.Client, url: str) -> httpx.Response:
    last = "?"
    for attempt in range(1, RETRIES + 1):
        try:
            r = client.get(url)
        except httpx.HTTPError as e:  # 메시지에 URL(키)이 들어갈 수 있다 — 종류만 남긴다
            last = type(e).__name__
        else:
            if r.status_code < 500:
                return r
            last = f"HTTP {r.status_code}"
        log.warning("재시도 %d/%d (%s)", attempt, RETRIES, last)
        time.sleep(2 * attempt)
    raise FetchError(f"요청 실패: {last}")


def fetch_page(
    client: httpx.Client, key: str, ds: ApiDataset, start: int, end: int
) -> tuple[bytes, int]:
    """한 페이지를 받아 (원문 바이트, list_total_count)를 돌려준다."""
    parts = [API_BASE, key, "json", ds.service, str(start), str(end)]
    parts += [quote(p) for p in ds.params]
    r = _get(client, "/".join(parts) + "/")
    body = json.loads(r.content)
    payload = body.get(ds.service)
    if r.status_code != 200 or payload is None:
        raise FetchError(f"{ds.dir_name} {start}-{end}: HTTP {r.status_code} {body.get('RESULT')}")
    if payload["RESULT"]["CODE"] != "INFO-000":
        raise FetchError(f"{ds.dir_name} {start}-{end}: {payload['RESULT']}")
    return r.content, int(payload["list_total_count"])


def fetch_dataset(
    client: httpx.Client, key: str, ds: ApiDataset, out_dir: Path
) -> dict[str, object]:
    d = out_dir / ds.dir_name
    d.mkdir(parents=True, exist_ok=True)
    calls = pages = 0
    start = 1
    total: int | None = None
    while total is None or start <= total:
        end = start + PAGE - 1
        path = d / f"{start:06d}-{end:06d}.json"
        if path.exists():  # 재실행: 받아 둔 페이지에서 총 건수만 읽는다
            total = int(json.loads(path.read_bytes())[ds.service]["list_total_count"])
        else:
            content, total = fetch_page(client, key, ds, start, end)
            path.write_bytes(content)
            calls += 1
            log.info("%s %d-%d / %d", ds.dir_name, start, min(end, total), total)
            time.sleep(0.2)
        pages += 1
        start = end + 1
    return {
        "dir": ds.dir_name,
        "service": ds.service,
        "params": list(ds.params),
        "dataset_id": ds.dataset_id,
        "source_url": dataset_url(ds.dataset_id),
        "list_total_count": total,
        "pages": pages,
        "calls": calls,
    }


def download_file(
    client: httpx.Client, name: str, form: dict[str, str], out_dir: Path
) -> dict[str, object]:
    path = out_dir / name
    disposition = ""
    if not path.exists():
        r = client.post(FILE_URL, data=form)
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or ctype.startswith("text/html"):
            msg = f"{name}: HTTP {r.status_code} {ctype} — 폼(seq/infSeq)이 바뀌었는지 확인"
            raise FetchError(msg)
        path.write_bytes(r.content)
        disposition = r.headers.get("content-disposition", "")
        log.info("%s %d bytes (%s)", name, len(r.content), disposition)
    return {
        "file": name,
        "dataset_id": form["infId"],
        "source_url": dataset_url(form["infId"]),
        "form": form,
        "content_disposition": disposition,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="서울 열린데이터광장 공간 데이터 수집 (T0.2)")
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y%m%d"), help="산출 폴더 날짜")
    ap.add_argument("--out", default=Path("data/raw"), type=Path)
    ap.add_argument(
        "--only", default=None, help="이 폴더 이름의 데이터셋만 (예: TbTraficWlkNet_seoul)"
    )
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx INFO는 URL(인증키)을 찍는다

    key = Settings().seoul_opendata_key
    if not key:
        raise SystemExit("SEOUL_OPENDATA_KEY 없음 — .env 확인")
    out_dir = args.out / f"seoul_spatial_{args.date}"
    out_dir.mkdir(parents=True, exist_ok=True)

    datasets: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    calls = 0
    with httpx.Client(timeout=60.0, headers={"User-Agent": "naru-fetch/0.5"}) as client:
        for ds in API_DATASETS:
            if args.only and ds.dir_name != args.only:
                continue
            info = fetch_dataset(client, key, ds, out_dir)
            datasets.append(info)
            calls += int(str(info["calls"]))
        for name, form in FILES:
            if args.only:
                break
            files.append(download_file(client, name, form, out_dir))

    meta = {
        "fetched_at": datetime.now(KST).isoformat(timespec="seconds"),
        "api_base": API_BASE,
        "page_size": PAGE,
        "calls": calls,
        "datasets": datasets,
        "files": files,
    }
    text = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    (out_dir / "_meta.json").write_text(text, "utf-8")
    log.info("완료: %s (API %d회)", out_dir, calls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
