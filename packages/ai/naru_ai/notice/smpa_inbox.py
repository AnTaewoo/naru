"""경찰청 '오늘의 주요집회' PDF inbox (T6.6) — 태우가 `<smpa>/inbox/` 에 넣은 PDF 를 워커가 읽는다.

- 경찰청 누리집은 robots.txt 가 막혀 있어 자동으로 받지 않는다(ROADMAP T6.6). 표는 SmpaPdfSource
  그대로 — 행 하나 = 문장 하나(T0.5). 머리글·날짜 줄이 다르면 `inbox/failed/` 로 옮기고 ERROR
- sentence_id = smpa-<집회 날짜>-r<행>-u<기준 작성 YYYYMMDDHHMM>: 같은 날짜의 고친 PDF(기준 작성이
  늦다)는 다시 파싱하고, 후보 ID 는 버전을 떼(candidate_stem) 같은 행을 덮는다
- 다 읽은 PDF 는 후보를 보낸 뒤 `<smpa>/<집회 날짜>.pdf` 로 옮긴다(있으면 -u<기준 작성>, 그것도
  있으면 -<sha256 앞 8>). `<smpa>` 에 똑같은 파일(sha256)이 이미 있으면 `inbox/duplicate/` 로 —
  보내지 않는다. 옮길 때마다 `<smpa>/inbox_manifest.jsonl` 에 한 줄(출처·넣은 시각·sha256·행 수)
- 볼 PDF = inbox 의 PDF + 옮긴 PDF 중 집회 날짜가 오늘 이후, 날짜마다 기준 작성이 가장 늦은 하나.
  태우가 처음 받은 옛 이름 3개(T0.5)는 sentences.jsonl 공지가 맡는다
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path

from naru_ai.ingest.topis_api import KST
from naru_ai.notice.source import SMPA_BOARD_URL, NoticeSentence, SmpaPdfSource

log = logging.getLogger(__name__)
MANIFEST = "inbox_manifest.jsonl"
LICENSE = "경찰청 공개 게시물 (별도 표기 없음)"  # data/MANIFEST.md notices/smpa 와 같다


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class SmpaPdf:
    path: Path  # 지금 위치 — inbox 면 옮기기 전
    dest: Path  # 옮길 곳(옮긴 PDF 는 path 와 같다). 근거 ref 는 이 경로
    event_date: date
    basis: datetime  # 기준 작성 = published_at
    sha256: str
    sentences: tuple[NoticeSentence, ...]

    @property
    def in_inbox(self) -> bool:
        return self.path != self.dest


@dataclass
class SmpaScan:
    publish: list[SmpaPdf] = field(default_factory=list)  # 날짜마다 하나 — 행을 파싱해 보낸다
    inbox: list[SmpaPdf] = field(default_factory=list)  # 옮길 것 (publish 에 없으면 바로)
    duplicates: list[Path] = field(default_factory=list)  # <smpa> 에 똑같은 파일이 있다


class SmpaInbox:
    def __init__(self, smpa_dir: Path, source_url: str = SMPA_BOARD_URL) -> None:
        self.dir = smpa_dir
        self.inbox = smpa_dir / "inbox"
        self.manifest = smpa_dir / MANIFEST
        self.reader = SmpaPdfSource(self.inbox, source_url)

    def scan(self, now: datetime) -> SmpaScan:
        self.inbox.mkdir(parents=True, exist_ok=True)
        today = now.astimezone(KST).date()
        out = SmpaScan()
        kept: list[SmpaPdf] = []
        for row in self._manifest_rows():
            path = self.dir / str(row["file"])
            if date.fromisoformat(str(row["event_date"])) >= today and path.exists():
                kept.append(self._read(path, path, set()))
        known = {sha256(p) for p in self.dir.glob("*.pdf")}
        taken: set[str] = set()  # 이번에 옮길 이름 — 같은 날짜 PDF 둘이 한 번에 와도 겹치지 않게
        for path in sorted(self.inbox.glob("*.pdf")):
            try:
                pdf = self._read(path, None, taken)
            except ValueError as e:  # 오늘의 주요집회 표가 아니다 — 사람이 볼 일
                self._move(path, self.inbox / "failed" / path.name)
                log.error("smpa pdf rejected", extra={"file": path.name, "error": str(e)[:300]})
                continue
            if pdf.sha256 in known:
                out.duplicates.append(path)
                continue
            known.add(pdf.sha256)
            taken.add(pdf.dest.name)
            kept.append(pdf)
            out.inbox.append(pdf)
        best: dict[date, SmpaPdf] = {}
        for pdf in kept:  # 옮긴 것 먼저 — 기준 작성이 같으면 옮긴 것
            cur = best.get(pdf.event_date)
            if cur is None or pdf.basis > cur.basis:
                best[pdf.event_date] = pdf
        out.publish = list(best.values())
        return out

    def archive(self, pdf: SmpaPdf, now: datetime, failed: list[str]) -> None:
        """다 읽은(또는 같은 날짜의 더 새 PDF 가 있는) inbox PDF 를 옮기고 manifest 에 한 줄."""
        received = datetime.fromtimestamp(pdf.path.stat().st_mtime, KST)
        self._move(pdf.path, pdf.dest)
        line = {
            "file": pdf.dest.name,
            "inbox_name": pdf.path.name,
            "sha256": pdf.sha256,
            "bytes": pdf.dest.stat().st_size,
            "rows": len(pdf.sentences),
            "event_date": pdf.event_date.isoformat(),
            "basis": pdf.basis.isoformat(),
            "received_at": received.isoformat(timespec="seconds"),
            "archived_at": now.astimezone(KST).isoformat(timespec="seconds"),
            "failed_rows": failed,
            "source_url": self.reader.source_url,
            "license": LICENSE,
        }
        with self.manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        log.info("smpa pdf archived", extra={"file": pdf.dest.name, "rows": len(pdf.sentences)})

    def set_aside(self, path: Path, now: datetime) -> None:
        """똑같은 파일이 이미 있다 — 지우지 않고 inbox/duplicate/ 로."""
        stamp = f"{now.astimezone(KST):%Y%m%dT%H%M%S}"
        self._move(path, self.inbox / "duplicate" / f"{stamp}_{path.name}")
        log.info("smpa pdf duplicate", extra={"file": path.name})

    def _read(self, path: Path, dest: Path | None, taken: set[str]) -> SmpaPdf:
        rows = self.reader.parse_file(path)  # 표·날짜 줄이 다르면 ValueError
        if not rows or rows[0].event_date is None:
            raise ValueError(f"{path.name}: 표에 행이 없다")
        event, basis, digest = rows[0].event_date, rows[0].published_at, sha256(path)
        target = dest or self._dest(event, basis, digest, taken)
        ver = f"-u{basis:%Y%m%d%H%M}"
        sentences = tuple(
            replace(s, sentence_id=s.sentence_id + ver, fields={**s.fields, "file": target.name})
            for s in rows
        )
        return SmpaPdf(path, target, event, basis, digest, sentences)

    def _dest(self, event: date, basis: datetime, digest: str, taken: set[str]) -> Path:
        stem = f"{event:%Y%m%d}"
        names = (f"{stem}.pdf", f"{stem}-u{basis:%Y%m%d%H%M}.pdf", f"{stem}-{digest[:8]}.pdf")
        for name in names:
            if name not in taken and not (self.dir / name).exists():
                return self.dir / name
        raise FileExistsError(f"{stem}: 옮길 이름이 다 있다 — {names}")

    def _manifest_rows(self) -> list[dict[str, object]]:
        if not self.manifest.exists():
            return []
        lines = self.manifest.read_text("utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    @staticmethod
    def _move(src: Path, dst: Path) -> None:
        """옮기기만 — 원문(data/raw)은 덮어쓰지 않는다."""
        if dst.exists():
            raise FileExistsError(f"{dst} 가 이미 있다")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
