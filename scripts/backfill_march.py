"""행진 모델 백필 (T7.16 뒤, 태우 2026-11-11 "채워").

T7.16 전에 접수된 행진 사건은 `closure_events.march` 가 비어 있어 키프레임 API 가
404(not_modeled)다. 모델은 접수 때만 계산하므로 기록해 둔 원천을 워커 재생 경로로 다시
접수시킨다 — CandidateIntake 가 사건 구역·행진 모델을 다시 만든다. 후보는 그때와 같으니
상태 값은 그대로고 사건 행의 march 만 채워진다.

  uv run python scripts/backfill_march.py --be http://127.0.0.1:5050 \\
      --smpa 261107 261108 261109 \\
      --topis-map 20261109T083719_selectAccAllListASC.json \\
      --incident 20261107T154053_AccInfo.json 20261109T145523_AccInfo.json \\
      --check ccaa9980c6ac 2e930ec6deeb

순서: 경찰청 PDF(LLM 은 기록 재생만 — client 없음, 기록 없는 문장은 건너뜀) → TOPIS
통제지도 목록(통제 도로 목록 기록이 있는 통제만 선) → 돌발 기록. 내용이 같은 배치는 BE 가
"batch duplicate" 로 버리므로(11/9 통제지도가 그랬다) `--suffix` 로 배치 id 를 바꿔 다시
보낸다. 돌발 근거는 접수 때 linked_evidence 로 다시 붙으니 덮여도 사라지지 않는다.
토큰은 .env NARU_INTERNAL_TOKEN. 운영 DB 에 쓴다 — 태우 승인 뒤에만.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from naru_ai.config import Settings
from naru_ai.publish import CandidatePublisher
from naru_ai.worker import IngestWorker

KST = timezone(timedelta(hours=9))
# 세 PDF(11/7~11/9)가 모두 "볼 것"이 되는 시각
SMPA_SCAN_AT = datetime(2026, 11, 6, 20, 0, tzinfo=KST)
log = logging.getLogger("backfill_march")


def march_status(be: str, event_id: str) -> str:
    r = httpx.get(f"{be}/closures/events/{event_id}/march", timeout=30)
    if r.status_code == 200:
        return "200"
    return f"{r.status_code} {r.json().get('error', {}).get('code')}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--be", required=True, help="BE 주소 (운영 http://127.0.0.1:5050)")
    ap.add_argument("--smpa", nargs="*", default=[], help="경찰청 PDF 날짜 접두 (raw/notices/smpa)")
    ap.add_argument("--topis-map", nargs="*", default=[], help="recorded/topis_web 목록 기록 파일")
    ap.add_argument("--incident", nargs="*", default=[], help="recorded/incident AccInfo 기록 파일")
    ap.add_argument("--check", nargs="*", default=[], help="끝나고 /march 상태를 볼 사건 id")
    ap.add_argument(
        "--suffix",
        default="",
        help="통제지도·돌발 배치 id 뒤에 붙일 말 — 내용이 같은 배치는 BE 가 중복으로 버리므로"
        "(batch duplicate) 다시 접수시키려면 준다 (예: backfill1111)",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    base = Settings()
    if not base.internal_token:
        print("NARU_INTERNAL_TOKEN 없음 — .env 확인", file=sys.stderr)
        return 2
    pub = CandidatePublisher(args.be, base.internal_token, backoff_s=1.0)
    recorded = base.data_dir / "recorded"
    before = {e: march_status(args.be, e) for e in args.check}

    if args.smpa:
        inbox = Path(tempfile.mkdtemp(prefix="backfill-smpa-")) / "inbox"
        inbox.mkdir()
        for pdf in (base.data_dir / "raw" / "notices" / "smpa").glob("*.pdf"):
            if any(pdf.name.startswith(p) for p in args.smpa):
                shutil.copy2(pdf, inbox / pdf.name)
        # client 없음 → LLM 기록 재생만
        worker = IngestWorker(base.model_copy(update={"smpa_dir": inbox.parent}), pub)
        got = worker.smpa_round(SMPA_SCAN_AT)
        log.info("smpa: 배치 %d — accepted %s", len(got), [r.accepted for r in got])

    for name in args.topis_map:
        update = {"topis_map_source": "recorded", "topis_map_record": recorded / "topis_web" / name}
        batch = IngestWorker(base.model_copy(update=update), pub).topis_map_batch()
        if batch is None:
            log.warning("topis map %s: 후보 없음", name)
            continue
        if args.suffix:
            batch = batch.model_copy(update={"batch_id": f"{batch.batch_id}-{args.suffix}"})
        done = pub.publish(batch).crosswalks_updated
        log.info("topis map %s: 후보 %d → 횡단보도 %d", name, len(batch.candidates), done)

    for name in args.incident:
        update = {"incident_source": "recorded", "incident_record": recorded / "incident" / name}
        batch = IngestWorker(base.model_copy(update=update), pub).incident_batch()
        if args.suffix:
            batch = batch.model_copy(update={"batch_id": f"{batch.batch_id}-{args.suffix}"})
        done = pub.publish(batch).crosswalks_updated
        log.info("incident %s: 후보 %d → 횡단보도 %d", name, len(batch.candidates), done)

    for e in args.check:
        print(f"{e}: {before[e]} → {march_status(args.be, e)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
