"""공지 문장 묶음 만들기 — `uv run python scripts/build_notices.py` (ROADMAP T0.5).

입력
  data/raw/notices/smpa/*.pdf          서울경찰청 '오늘의 주요집회' (태우가 매일 수동으로 받아 둠)
  data/recorded/topis_notice/*.json    TOPIS 공지 NoticeList 응답 기록.
                                       없거나 --topis 를 주면 1회 호출해 기록
출력
  data/raw/notices/sentences.jsonl     문장 레코드 (naru_ai.notice.source.NoticeSentence.to_json)
  data/raw/notices/sentences_meta.json 건수·출처·기록 파일

TOPIS는 열린데이터광장 키(SEOUL_OPENDATA_KEY)로 xml만 받을 수 있다(json은 ERROR-301).
한 번에 최대 1,000건.
기록 형식은 real-data-testing §3 (api, endpoint, params(키 제거), called_at, status, raw).
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from naru_ai.notice.source import TOPIS_SERVICE, SmpaPdfSource, TopisNoticeSource

log = logging.getLogger("build_notices")
KST = timezone(timedelta(hours=9))
API_BASE = "http://openapi.seoul.go.kr:8088"
TOPIS_CATEGORIES = ("통제안내", "버스안내")  # 공지 분류 5종 중 통제와 관련된 둘


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    seoul_opendata_key: str = ""


def record_topis(recorded_dir: Path, limit: int) -> Path:
    """NoticeList 1..limit 를 한 번 호출해 원문 그대로 기록한다. 키는 저장하지 않는다."""
    key = Settings().seoul_opendata_key
    if not key:
        raise SystemExit("SEOUL_OPENDATA_KEY 없음 — .env 확인")
    endpoint = f"{API_BASE}/<키>/xml/{TOPIS_SERVICE}/1/{limit}/"
    called_at = datetime.now(KST)
    r = httpx.get(
        endpoint.replace("<키>", key), timeout=60.0, headers={"User-Agent": "naru-fetch/0.5"}
    )
    recorded_dir.mkdir(parents=True, exist_ok=True)
    path = recorded_dir / f"{called_at:%Y%m%dT%H%M%S}.json"
    path.write_text(
        json.dumps(
            {
                "api": "topis_notice",
                "endpoint": endpoint,
                "params": {"service": TOPIS_SERVICE, "type": "xml", "start": 1, "end": limit},
                "called_at": called_at.isoformat(timespec="seconds"),
                "status": r.status_code,
                "raw": r.text,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        "utf-8",
    )
    log.info(
        "TOPIS NoticeList 1-%d 기록 → %s (HTTP %d, %d bytes)",
        limit,
        path,
        r.status_code,
        len(r.content),
    )
    return path


def load_recorded(recorded_dir: Path) -> list[tuple[str, datetime]]:
    out: list[tuple[str, datetime]] = []
    for path in sorted(recorded_dir.glob("*.json")):
        rec = json.loads(path.read_text("utf-8"))
        if rec.get("status") == 200:
            out.append((rec["raw"], datetime.fromisoformat(rec["called_at"])))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공지 문장 묶음 만들기 (T0.5)")
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--recorded", type=Path, default=Path("data/recorded"))
    ap.add_argument(
        "--topis", action="store_true", help="TOPIS NoticeList를 지금 1회 호출해 기록한다"
    )
    ap.add_argument(
        "--topis-limit", type=int, default=300, help="한 번에 받을 최신 공지 수 (≤1000)"
    )
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    smpa_dir = args.raw / "notices" / "smpa"
    topis_dir = args.recorded / "topis_notice"
    if args.topis or not any(topis_dir.glob("*.json")):
        record_topis(topis_dir, args.topis_limit)

    smpa = SmpaPdfSource(smpa_dir).sentences()
    topis = TopisNoticeSource(load_recorded(topis_dir), categories=TOPIS_CATEGORIES).sentences()
    sentences = [*smpa, *topis]
    ids = [s.sentence_id for s in sentences]
    if len(ids) != len(set(ids)):
        raise SystemExit("sentence_id 중복")

    out_dir = args.raw / "notices"
    jsonl = out_dir / "sentences.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        for s in sentences:
            f.write(json.dumps(s.to_json(), ensure_ascii=False) + "\n")
    meta = {
        "built_at": datetime.now(KST).isoformat(timespec="seconds"),
        "smpa": {
            "files": sorted(p.name for p in smpa_dir.glob("*.pdf")),
            "sentences": len(smpa),
            "per_file": {
                name: sum(1 for s in smpa if s.fields.get("file") == name)
                for name in sorted(p.name for p in smpa_dir.glob("*.pdf"))
            },
        },
        "topis": {
            "recorded": sorted(p.name for p in topis_dir.glob("*.json")),
            "categories": list(TOPIS_CATEGORIES),
            "notices": len({s.notice_id for s in topis}),
            "sentences": len(topis),
        },
        "total": len(sentences),
    }
    (out_dir / "sentences_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    log.info(
        "문장 %d개 (smpa %d, topis %d / 공지 %d) → %s",
        len(sentences),
        len(smpa),
        len(topis),
        meta["topis"]["notices"],
        jsonl,
    )  # type: ignore[index]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
