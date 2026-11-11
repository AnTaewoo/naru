"""TOPIS 공지 아카이브 깊이 기록 (T7.18, 멘토링 T-D 조사) — 원문만 받아 둔다. 본문 수집 없음.

  uv run python scripts/record_topis_archive.py robots              # topis.seoul.go.kr/robots.txt
  uv run python scripts/record_topis_archive.py board [--page N]    # 게시판 목록 쪽(HTML 틀)
  uv run python scripts/record_topis_archive.py ajax --page N       # 목록 AJAX(실제 글 목록 json)
  uv run python scripts/record_topis_archive.py api                 # NoticeList(OA-22861) 끝 찾기
  uv run python scripts/record_topis_archive.py dump --last 3825    # 1000건씩 전부(연도·분류 세기)
세기·들여다보기(호출 없음)는 scripts/topis_archive_stats.py.

웹(robots·board)은 ADR-011 E — NaruBot UA, 같은 곳 10분(마지막 기록이 10분 안이면 거절),
recorded/topis_web/<ts>_robots.txt · <ts>_openNoticeList_p<N>.html 에 그대로.
api 는 열린데이터광장 키(SEOUL_OPENDATA_KEY) — 1/5 로 모양을 보고, 글 번호 순으로 끝 인덱스를
탐색(지수 → 이분, 호출 20회 안)해 마지막 5건을 받는다. 기록은
recorded/topis_notice_archive/<ts>_NoticeList.json — 운영 피드 기록 topis_notice 와 다른 폴더
(테스트·워커가 그 폴더 전체를 읽는다).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from naru_ai.config import Settings
from naru_ai.ingest.topis_api import SeoulOpenApi

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "NaruBot/0.1 (+https://naru.antaewoo.com)"}
BOARD_URL = "https://topis.seoul.go.kr/notice/openNoticeList.do"
ROBOTS_URL = "https://topis.seoul.go.kr/robots.txt"
MIN_GAP = timedelta(minutes=10)
# 운영 피드 기록(recorded/topis_notice, 1/50)과 섞이지 않게 — 테스트·워커가 그 폴더 전체를 읽는다
ARCHIVE = "topis_notice_archive"
log = logging.getLogger("record_topis_archive")


def last_web_fetch(folder: Path) -> datetime | None:
    stamps = []
    for p in folder.glob("*"):
        m = re.match(r"(\d{8}T\d{6})_(robots|openNoticeList|selectNoticeList)", p.name)
        if m:
            stamps.append(datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=KST))
    return max(stamps) if stamps else None


AJAX_URL = "https://topis.seoul.go.kr/notice/selectNoticeList.do"
# 게시판 쪽의 #searchForm 그대로(openNoticeList_p1.html 의 fn_getNoticeList) — 분류 02 = 공지
AJAX_FORM = {"recordPerPage": "10", "pageSize": "5", "jsFunction": "fn_getNoticeList"}
AJAX_FORM |= {"bdwrSeq": "", "blbdDivCd": "02", "bdwrDivCd": "", "tabGubun": "", "boardSearch": ""}


def fetch_web(
    folder: Path,
    url: str,
    name: str,
    params: dict[str, str] | None,
    post: dict[str, str] | None = None,
) -> Path:
    last = last_web_fetch(folder)
    now = datetime.now(KST)
    if last is not None and now - last < MIN_GAP:
        raise SystemExit(f"같은 곳 10분 — 마지막 {last:%H:%M:%S}, {(last + MIN_GAP):%H:%M:%S} 뒤에")
    if post is not None:
        r = httpx.post(url, data=post, headers=UA, timeout=30, follow_redirects=True)
    else:
        r = httpx.get(url, params=params, headers=UA, timeout=30, follow_redirects=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{now:%Y%m%dT%H%M%S}_{name}"
    head = (
        f"<!-- fetched {now.isoformat(timespec='seconds')} GET {r.url} HTTP {r.status_code} -->\n"
    )
    path.write_text(
        (head if name.endswith(".html") else head.replace("<!-- ", "# ").replace(" -->", ""))
        + r.text,
        "utf-8",
    )
    log.info("web %s HTTP %s %d bytes → %s", r.url, r.status_code, len(r.text), path.name)
    return path


def notice_page(api: SeoulOpenApi, start: int, end: int) -> tuple[str, int, list[dict[str, str]]]:
    """(RESULT/CODE, list_total_count, rows) — rows 는 태그 → 글자."""
    rec = api.call(ARCHIVE, "NoticeList", start, end)
    root = ET.fromstring(rec.raw)
    code = root.findtext("RESULT/CODE") or root.findtext("CODE") or ""
    total = int(root.findtext("list_total_count") or 0)
    rows = [{c.tag: (c.text or "") for c in row} for row in root.findall("row")]
    log.info("NoticeList %d/%d → %s total=%s rows=%d", start, end, code, total, len(rows))
    return code, total, rows


def probe_api(settings: Settings, recorded: Path) -> None:
    key = settings.seoul_opendata_key.get_secret_value()
    if not key:
        raise SystemExit("SEOUL_OPENDATA_KEY 없음 — .env 확인")
    api = SeoulOpenApi(key, recorded, settings.seoul_api_url)
    calls = 1
    code, total, rows = notice_page(api, 1, 5)
    first = rows[0].get("bdwr_seq") if rows else None
    print(f"1/5: {code} list_total_count={total} rows={len(rows)} 첫 글 번호={first}")
    print("필드:", ", ".join(rows[0].keys()) if rows else "-")
    # list_total_count 가 요청 수와 같으면 전체 수가 아니다 — 있는 인덱스를 지수로 넓히고
    # 이분으로 좁힌다
    ok, bad = 1, None
    for n in (1000, 2000, 4000, 8000, 16000, 32000):
        calls += 1
        _, _, r = notice_page(api, n, n)
        if r:
            ok = n
        else:
            bad = n
            break
    if bad is None:
        raise SystemExit("32000 에도 글이 있다 — 더 넓혀야 한다")
    while bad - ok > 1 and calls < 20:
        mid = (ok + bad) // 2
        calls += 1
        _, _, r = notice_page(api, mid, mid)
        ok, bad = (mid, bad) if r else (ok, mid)
    calls += 1
    _, _, tail = notice_page(api, max(1, ok - 4), ok)
    print(f"마지막 인덱스 {ok} (호출 {calls}회). 끝 5건:")
    for row in tail:
        print("  ", {k: v[:60] for k, v in row.items()})


def dump_api(settings: Settings, recorded: Path, last: int) -> None:
    """1..last 를 1000건씩(열린데이터광장 한 번 상한) 받아 둔다 — 연도별 건수·분류를 세기 위해.
    공식 API 라 본문(bdwr_cts)이 같이 온다(웹 게시판은 긁지 않는다)."""
    key = settings.seoul_opendata_key.get_secret_value()
    if not key:
        raise SystemExit("SEOUL_OPENDATA_KEY 없음 — .env 확인")
    api = SeoulOpenApi(key, recorded, settings.seoul_api_url)
    years: dict[str, int] = {}
    divs: dict[str, int] = {}
    n = 0
    for start in range(1, last + 1, 1000):
        _, _, rows = notice_page(api, start, min(start + 999, last))
        for row in rows:
            n += 1
            years[row.get("create_date", "")[:4]] = years.get(row.get("create_date", "")[:4], 0) + 1
            div = row.get("bdwr_div_nm") or "(없음)"
            divs[div] = divs.get(div, 0) + 1
    print(f"받은 글 {n}건")
    print("연도별:", dict(sorted(years.items())))
    print("분류별:", divs)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("what", choices=["robots", "board", "ajax", "api", "dump"])
    ap.add_argument("--page", type=int, default=1, help="board: 쪽 번호")
    ap.add_argument("--last", type=int, default=3825, help="dump: 마지막 인덱스 (api 로 찾은 값)")
    ap.add_argument("--per-page", type=int, default=10, help="ajax: 쪽당 글 수")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings()
    recorded = settings.data_dir / "recorded"
    web = recorded / "topis_web"
    if args.what == "robots":
        fetch_web(web, ROBOTS_URL, "robots.txt", None)
    elif args.what == "board":
        params = {"pageIndex": str(args.page)} if args.page > 1 else None
        fetch_web(web, BOARD_URL, f"openNoticeList_p{args.page}.html", params)
    elif args.what == "ajax":
        form = {**AJAX_FORM, "pageIndex": str(args.page), "recordPerPage": str(args.per_page)}
        path = fetch_web(web, AJAX_URL, f"selectNoticeList_p{args.page}.json", None, post=form)
        body = json.loads(path.read_text("utf-8").split("\n", 1)[1])
        print("키:", list(body.keys()))
        print({k: v for k, v in body.items() if not isinstance(v, list)})
        for row in body.get("rows", []):
            print(
                "  ",
                {
                    k: str(v)[:50]
                    for k, v in row.items()
                    if k
                    in ("bdwrSeq", "bdwrDivCd", "bdwrTtlNm", "createDate", "regDt", "updateDate")
                },
            )
    elif args.what == "api":
        probe_api(settings, recorded)
    else:
        dump_api(settings, recorded, args.last)
    return 0


if __name__ == "__main__":
    sys.exit(main())
