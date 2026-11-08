"""서울 버스 노선별 정류소 수집 CLI — `make fetch SRC=bus_routes` (ROADMAP T6.2, ADR-013 D).

열린데이터광장 OA-1095 "서울시 버스노선별 정류소 정보"(매월 XLSX, 키 없음). 데이터셋 페이지에서 가장
최근 파일의 seq 를 읽어 nio_download.do 로 한 번 받는다(robots.txt: data.seoul.go.kr 전부 허용,
datafile.seoul.go.kr 은 robots.txt 없음 — 2026-11-08 확인). 같은 곳 두 번 이상 부르지 않는다.

산출: data/raw/bus_routes_<YYYYMMDD>/
  OA-1095.xlsx   받은 그대로 (원래 이름은 _meta.json 의 file_name)
  _meta.json     출처·폼·sha256·칸 이름·행 수
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from openpyxl import load_workbook

log = logging.getLogger("fetch_bus_routes")

DATASET = "OA-1095"
PAGE_URL = f"https://data.seoul.go.kr/dataList/{DATASET}/S/1/datasetView.do"
FILE_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
UA = {"User-Agent": "NaruBot/0.1 (+https://naru.antaewoo.com)"}  # ADR-011 E
KST = timezone(timedelta(hours=9))
LATEST = re.compile(r"title=\"([^\"]+\.xlsx)\" onclick=\"javascript:downloadFile\('(\d+)'\);\"")
# 페이지에 infSeq 가 둘(API 폼 4, 파일 폼 2) — 파일 폼(frmFile) 것을 쓴다 (2026-11-08)
INF_SEQ = re.compile(r"name=\"frmFile\".*?name=\"infSeq\" value=\"(\d+)\"", re.S)


def latest_file(page: str) -> tuple[str, str, str]:
    """(파일 이름, seq, infSeq) — 파일내려받기 표의 첫 줄이 가장 최근 파일."""
    m, inf = LATEST.search(page), INF_SEQ.search(page)
    if m is None or inf is None:
        raise SystemExit(f"{DATASET}: 페이지에서 파일 목록을 못 찾았다 — 페이지 형식이 바뀌었나")
    return m.group(1), m.group(2), inf.group(1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="서울 버스 노선별 정류소 수집 (T6.2)")
    ap.add_argument("--date", default=datetime.now(KST).strftime("%Y%m%d"), help="산출 폴더 날짜")
    ap.add_argument("--out", default=Path("data/raw"), type=Path)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out_dir = args.out / f"bus_routes_{args.date}"
    path = out_dir / f"{DATASET}.xlsx"
    if path.exists():
        raise SystemExit(f"이미 있다: {path} — 받은 뒤 고치지 않는다(CLAUDE.md §2)")
    with httpx.Client(timeout=120.0, headers=UA, follow_redirects=True) as client:
        page = client.get(PAGE_URL)
        page.raise_for_status()
        name, seq, inf_seq = latest_file(page.text)
        form = {"infId": DATASET, "seq": seq, "infSeq": inf_seq}
        r = client.post(FILE_URL, data=form)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or ctype.startswith("text/html"):
        raise SystemExit(f"{name}: HTTP {r.status_code} {ctype} — 폼(seq/infSeq) 확인")
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    sheet = load_workbook(path, read_only=True).worksheets[0]
    rows = sheet.iter_rows(values_only=True)
    columns = [str(c) for c in next(rows)]
    n = sum(1 for _ in rows)
    meta = {
        "fetched_at": datetime.now(KST).isoformat(timespec="seconds"),
        "dataset_id": DATASET,
        "source_url": PAGE_URL,
        "file_name": name,
        "form": form,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "columns": columns,
        "rows": n,
        "license": "공공누리 1유형 (열린데이터광장)",
    }
    text = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    (out_dir / "_meta.json").write_text(text, "utf-8")
    log.info("완료: %s — %s, %d행, 칸 %s", path, name, n, columns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
