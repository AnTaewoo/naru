"""T7.18 조사 기록 읽기 (호출 없음) — scripts/record_topis_archive.py 가 받아 둔 것을 센다.

uv run python scripts/topis_archive_stats.py stats      # NoticeList 아카이브 분류·연도·문구
uv run python scripts/topis_archive_stats.py inspect    # 게시판 쪽 HTML 의 건수·쪽 파라미터·AJAX
uv run python scripts/topis_archive_stats.py relocate   # 11/11 처음 topis_notice 에 남긴 것 옮기기
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from naru_ai.config import Settings

# 운영 피드 기록(recorded/topis_notice, 1/50)과 섞이지 않게 — 테스트·워커가 그 폴더 전체를 읽는다
ARCHIVE = "topis_notice_archive"


def stats(recorded: Path) -> None:
    """dump 로 받아 둔 기록(1000건 묶음들)을 읽어 분류·연도·문구를 센다. 호출 없음."""
    files = sorted((recorded / ARCHIVE).glob("*_NoticeList.json"))
    rows: dict[str, dict[str, str]] = {}
    for f in files:
        try:
            root = ET.fromstring(json.loads(f.read_text("utf-8"))["raw"])
        except ET.ParseError as e:
            print(f"건너뜀 {f.name}: xml 아님 ({e})")
            continue
        for row in root.findall("row"):
            d = {c.tag: (c.text or "") for c in row}
            if d.get("bdwr_seq"):
                rows[d["bdwr_seq"]] = d
    print(f"기록 파일 {len(files)}개, 글(번호 기준) {len(rows)}건")
    control = [d for d in rows.values() if d.get("bdwr_div_nm") == "통제안내"]
    by_year: dict[str, int] = {}
    for d in control:
        by_year[d["create_date"][:4]] = by_year.get(d["create_date"][:4], 0) + 1
    print("통제안내 연도별:", dict(sorted(by_year.items())))
    words = ("집회", "행진", "마라톤", "통제일시", "통제구간", "통제시간", "우회")
    for w in words:
        n = sum(1 for d in control if w in d.get("bdwr_ttl_nm", "") + d.get("bdwr_cts", ""))
        print(f"  통제안내 중 '{w}' 포함 {n}건")
    both = sum(
        1
        for d in control
        if "통제일시" in d.get("bdwr_cts", "") and "통제구간" in d.get("bdwr_cts", "")
    )
    print(f"  통제안내 중 통제일시+통제구간 둘 다 {both}건")
    dates = sorted(d["create_date"] for d in rows.values() if d.get("create_date"))
    print("가장 오래된/최신 create_date:", dates[0], dates[-1])


def relocate(recorded: Path) -> None:
    """2026-11-11 처음 돌릴 때 topis_notice 에 남긴 탐색·dump 기록(1/50 이 아닌 요청)을
    topis_notice_archive 로 옮긴다 — 내용은 그대로, 이름도 그대로. 한 번 쓰고 나면 할 일이 없다."""
    src, dst = recorded / "topis_notice", recorded / ARCHIVE
    dst.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in sorted(src.glob("20261111T14*_NoticeList.json")):
        params = json.loads(f.read_text("utf-8")).get("params", {})
        if (params.get("start"), params.get("end")) == (1, 50):
            continue
        f.rename(dst / f.name)
        moved += 1
    print(f"옮김 {moved}개 → {dst}")


def inspect_board(recorded: Path) -> None:
    """받아 둔 게시판 목록 쪽에서 전체 건수·쪽 넘김 파라미터·날짜 범위를 읽어 출력한다."""
    for f in sorted((recorded / "topis_web").glob("*_openNoticeList_p*.html")):
        t = f.read_text("utf-8")
        print("==", f.name, len(t), "bytes")
        for m in re.finditer(r"(?:총|전체)\s*[^<]{0,12}?(\d[\d,]*)\s*건", t):
            print("  건수:", m.group(0))
        params = sorted(set(re.findall(r"name=\"(\w*(?:page|Page|pageNo|cpage)\w*)\"", t)))
        print("  쪽 파라미터 후보:", params)
        calls = sorted(set(re.findall(r"(?:fn_?[Pp]age\w*|goPage|pageMove)\(([^)]*)\)", t)))
        print("  쪽 넘김 호출:", calls[:12])
        dates = re.findall(r"20\d\d[.-]\d\d[.-]\d\d", t)
        print("  날짜:", dates[:2], "...", dates[-2:], f"({len(dates)}개)")
        print("  글 링크:", len(re.findall(r"openNoticeView\.do", t)))
        print("  .do 주소:", sorted(set(re.findall(r"[\w/.-]*/\w+\.do", t)))[:20])
        i = t.find("function fn_getNoticeList")
        if i >= 0:
            print("  fn_getNoticeList:", re.sub(r"\s+", " ", t[i : i + 900]))
        print(
            "  form 입력:", re.findall(r"<input[^>]*name=\"(\w+)\"[^>]*value=\"([^\"]*)\"", t)[:12]
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("what", choices=["stats", "inspect", "relocate"])
    args = ap.parse_args()
    recorded = Settings().data_dir / "recorded"
    if args.what == "stats":
        stats(recorded)
    elif args.what == "inspect":
        inspect_board(recorded)
    else:
        relocate(recorded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
