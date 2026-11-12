"""서울 실시간 도시데이터(OA-21285) 주요 장소 목록 xlsx 받기 (T7.19 — 장소 고르기용).

  uv run python scripts/fetch_citydata_areas.py            # make fetch SRC=citydata_areas

열린데이터광장 데이터셋 페이지의 첨부 "서울시 주요 121장소 목록.xlsx" 를 찾아
raw/citydata_areas_<날짜>/ 에 그대로 둔다(페이지 1회 + 파일 1회, NaruBot — ADR-011 E,
data.seoul.go.kr robots 는 전부 허용). 받은 뒤 열 이름·행 수를 출력한다 — MANIFEST 에 적을 값.
좌표 열이 없으면 장소 중심은 citydata 응답으로 만든다.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import geopandas as gpd
import httpx
import openpyxl

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "NaruBot/0.1 (+https://naru.antaewoo.com)"}
PAGE = "https://data.seoul.go.kr/dataList/OA-21285/A/1/datasetView.do"
DOWNLOAD = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do"


def inspect_page(out: Path) -> int:
    """받아 둔 페이지에서 첨부·다운로드 링크 후보를 보여 준다(요청 없음)."""
    html = (out / "datasetView.html").read_text("utf-8")
    for m in re.finditer(r"<a[^>]*>[^<]*</a>", html):
        a = m.group(0)
        if any(k in a for k in ("xlsx", "121", "ownload", "첨부")):
            print(re.sub(r"\s+", " ", a)[:300])
    i = html.find("function downloadFile")
    if i >= 0:
        print("function:", re.sub(r"\s+", " ", html[i : i + 700]))
    j = html.find('name="frmFile"')
    if j >= 0:
        k = html.find("</form>", j)
        print("form:", re.sub(r"\s+", " ", html[html.rfind("<form", 0, j) : k + 7]))
    for m in re.finditer(r"downloadFile\('\d+'\)", html):
        ctx = re.sub(r"\s+", " ", html[max(0, m.start() - 250) : m.end() + 150])
        print("ctx:", ctx)
    return 0


def main() -> int:
    now = datetime.now(KST)
    out = Path("data") / "raw" / f"citydata_areas_{now:%Y%m%d}"
    out.mkdir(parents=True, exist_ok=True)
    if "--inspect" in sys.argv:
        return inspect_page(out)
    # 페이지를 먼저 받고(첨부 표에서 seq 를 읽는다) 같은 세션으로 내려받는다
    client = httpx.Client(headers=UA, timeout=120, follow_redirects=True)
    page = client.get(PAGE)
    page.raise_for_status()
    (out / "datasetView.html").write_text(page.text, "utf-8")
    html = page.text
    # 첨부 표의 <span title="<파일 이름>" onclick="downloadFile('<seq>')"> — 폼 frmFile 을
    # POST (infId, seq, infSeq) 로 datafile.seoul.go.kr 에 보낸다 (페이지의 downloadFile 그대로)
    files = dict(
        re.findall(r'title="([^"]+)" onclick="javascript:downloadFile\(\'(\d+)\'\);"', html)
    )
    wanted = {name: seq for name, seq in files.items() if "121장소" in name}
    if not wanted:
        print("121장소 첨부를 못 찾음:", files, file=sys.stderr)
        return 2
    # 숨은 값은 frmFile 폼 안의 것만 — 페이지의 다른 폼에도 infSeq 가 있다(값이 다르다)
    f0 = html.find('name="frmFile"')
    frm = html[f0 : html.find("</form>", f0)] if f0 >= 0 else ""
    inf_id = re.search(r'name="infId" value="([^"]+)"', frm)
    inf_seq = re.search(r'name="infSeq" value="([^"]+)"', frm)
    meta: dict[str, object] = {
        "page": PAGE,
        "fetched_at": now.isoformat(timespec="seconds"),
        "files": {},
    }
    for name, seq in sorted(wanted.items()):
        # 빈 seqNo 가 끼면 "잘못된 접근" — infId·seq·infSeq 만 GET 파라미터로 (11/11 확인)
        form = {
            "infId": inf_id.group(1) if inf_id else "OA-21285",
            "seq": seq,
            "infSeq": inf_seq.group(1) if inf_seq else "2",
            "useCache": "false",
        }
        headers = {"Referer": PAGE, "Origin": "https://data.seoul.go.kr"}
        r = client.get(DOWNLOAD, params=form, headers=headers)
        r.raise_for_status()
        if len(r.content) < 1000 and b"<html" in r.content[:200].lower():
            print("첨부 대신 안내 HTML:", r.text[:160], file=sys.stderr)
            print("요청:", r.request.method, str(r.request.url), file=sys.stderr)
            return 3
        dest = out / name
        dest.write_bytes(r.content)
        info = {
            "seq": seq,
            "bytes": len(r.content),
            "sha256": hashlib.sha256(r.content).hexdigest(),
        }
        meta["files"][name] = info  # type: ignore[index]  # dict[str, object] 안의 dict
        print("받음:", name, info["bytes"], "B", str(info["sha256"])[:16])
    meta["license"] = "공공누리 1유형 (OA-21285 페이지 표기)"
    (out / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", "utf-8")
    for name in wanted:
        path = out / name
        if name.endswith(".xlsx"):
            wb = openpyxl.load_workbook(path, read_only=True)
            for ws in wb.worksheets:
                rows = list(ws.iter_rows(values_only=True))
                print(f"시트 {ws.title}: {len(rows)}행, 첫 줄 {rows[0] if rows else None}")
                for row in rows[1:3]:
                    print("  ", row)
        elif name.endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                print("zip:", z.namelist())
                z.extractall(out / "areas_shp")
            shp = next((out / "areas_shp").rglob("*.shp"), None)
            if shp is not None:
                gdf = gpd.read_file(shp)
                print("shp:", len(gdf), "행, crs", gdf.crs, "열", list(gdf.columns))
                print(gdf.head(3).drop(columns="geometry").to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
