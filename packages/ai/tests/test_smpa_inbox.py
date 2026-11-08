"""T6.6 — 경찰청 '오늘의 주요집회' PDF inbox: 감지 → 표 → 버전 붙은 문장 → 옮기기·manifest.

입력은 실제 PDF 3개(raw notices/smpa — 태우가 2026-11-07 받음, MANIFEST notices/smpa)를 임시 smpa
폴더에 복사해 쓴다(원문은 안 건드린다). 행 수·첫 행은 PDF 를 열어 확인한 값(test_notice_source 와
같다), 머리 '(2026. 11. 6. 18:00 기준 작성)' 은 세 파일 다 같다.
"""

import json
import shutil
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from naru_ai.config import Settings
from naru_ai.notice.smpa_inbox import SmpaInbox, sha256
from naru_ai.publish import CandidatePublisher, PublishError
from naru_ai.worker import IngestWorker

KST = ZoneInfo("Asia/Seoul")
NOV7 = "261107(토) 오늘의 주요집회.pdf"
NOV8 = "261108(일) 오늘의 주요집회.pdf"
NOV9 = "261109(월) 오늘의 주요집회.pdf"
EVE = datetime(2026, 11, 8, 20, 0, tzinfo=KST)  # 11/9 PDF 를 전날 저녁에 넣었다


@pytest.fixture
def smpa(tmp_path: Path) -> Path:
    return tmp_path / "smpa"


def _drop(smpa: Path, src: Path) -> Path:
    (smpa / "inbox").mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy2(src, smpa / "inbox" / src.name))


def test_scan_reads_the_table_with_versioned_ids(smpa_dir: Path, smpa: Path) -> None:
    _drop(smpa, smpa_dir / NOV9)
    scan = SmpaInbox(smpa).scan(EVE)
    assert scan.inbox == scan.publish and [p.dest.name for p in scan.publish] == ["20261109.pdf"]
    pdf = scan.publish[0]
    assert pdf.event_date == date(2026, 11, 9)  # 머리 '2026. 11. 9.(월)'
    assert pdf.basis == datetime(2026, 11, 6, 18, 0, tzinfo=KST)  # 기준 작성
    assert [s.sentence_id for s in pdf.sentences] == [
        f"smpa-20261109-r0{i}-u202611061800"
        for i in range(1, 5)  # 표 4행
    ]
    assert pdf.sentences[0].text.startswith("10:30~13:00 하나증권 앞 → 금감원·여의도역")
    assert pdf.sentences[0].fields["file"] == "20261109.pdf"
    assert pdf.sha256 == sha256(smpa_dir / NOV9)


def test_archive_moves_and_watches_until_the_day_passes(smpa_dir: Path, smpa: Path) -> None:
    inbox = SmpaInbox(smpa)
    _drop(smpa, smpa_dir / NOV9)
    inbox.archive(inbox.scan(EVE).publish[0], EVE, [])
    assert not list((smpa / "inbox").glob("*.pdf"))
    assert sha256(smpa / "20261109.pdf") == sha256(smpa_dir / NOV9)  # 옮기기만, 내용 그대로
    line = json.loads((smpa / "inbox_manifest.jsonl").read_text("utf-8"))
    assert (line["file"], line["inbox_name"], line["rows"]) == ("20261109.pdf", NOV9, 4)
    assert (line["event_date"], line["basis"]) == ("2026-11-09", "2026-11-06T18:00:00+09:00")
    assert line["sha256"] == sha256(smpa_dir / NOV9) and line["failed_rows"] == []
    # 옮긴 PDF 는 그날까지 계속 본다(BE 를 다시 채울 수 있게), 지난 날짜는 안 본다
    again = inbox.scan(EVE)
    assert [p.path.name for p in again.publish] == ["20261109.pdf"] and again.inbox == []
    assert inbox.scan(datetime(2026, 11, 10, 0, 0, tzinfo=KST)).publish == []


def test_same_file_again_is_set_aside(smpa_dir: Path, smpa: Path) -> None:
    inbox = SmpaInbox(smpa)
    smpa.mkdir()
    shutil.copy2(smpa_dir / NOV9, smpa / NOV9)  # T0.5 처럼 옛 이름으로 이미 있다
    _drop(smpa, smpa_dir / NOV9)  # 같은 파일을 또 넣었다
    scan = inbox.scan(EVE)
    assert scan.duplicates == [smpa / "inbox" / NOV9] and scan.inbox == scan.publish == []
    inbox.set_aside(scan.duplicates[0], EVE)
    assert [p.name for p in (smpa / "inbox" / "duplicate").iterdir()] == [f"20261108T200000_{NOV9}"]


def test_two_days_dropped_together(smpa_dir: Path, smpa: Path) -> None:
    for name in (NOV7, NOV8):
        _drop(smpa, smpa_dir / name)
    scan = SmpaInbox(smpa).scan(datetime(2026, 11, 6, 20, 0, tzinfo=KST))
    assert sorted(p.dest.name for p in scan.publish) == ["20261107.pdf", "20261108.pdf"]
    assert sorted(len(p.sentences) for p in scan.publish) == [3, 6]  # 11/8 3행, 11/7 6행


def test_round_keeps_the_pdf_when_sending_fails(smpa_dir: Path, smpa: Path) -> None:
    # 11/9 4행은 기록 notice_v2 smpa-20261109-r0{1..4}-u202611061800(2026-11-08 live) 재생 → 후보 2
    # (r01 구간, r02 출발점). BE 가 없으면(127.0.0.1:9, 실제 연결 거부) 보내기 실패 → PDF 는 inbox
    # 그대로, manifest 도 없다 — 다음 번에 다시
    _drop(smpa, smpa_dir / NOV9)
    publisher = CandidatePublisher("http://127.0.0.1:9", "unused", backoff_s=0.0)
    w = IngestWorker(Settings(NARU_SMPA_DIR=str(smpa)), publisher)
    with pytest.raises(PublishError, match="회 실패"):
        w.smpa_round(EVE)
    assert [p.name for p in (smpa / "inbox").glob("*.pdf")] == [NOV9]
    assert not (smpa / "inbox_manifest.jsonl").exists() and w.parse_failed == set()
