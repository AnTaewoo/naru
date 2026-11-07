"""RuleBaseline — 규칙만으로 공지를 파싱하는 기준선 (T4.3, "AI 가 필요한가"의 비교 대상).

시간 정규식 + 화살표(→ ↔)·물결(~) 분해 + 규칙서 §1.1 약칭(R·出) + 꺾쇠 힌트. 문자열만 본다.
출력은 Claude 와 같은 NoticeOutput 이라 같은 eval 로 잰다. 좌표 없음. 모르면 null.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from naru_ai.llm.notice_schema import (
    Impact,
    ImpactReason,
    Kind,
    Lanes,
    NoticeItem,
    NoticeOutput,
    Point,
    Segment,
    Span,
    Window,
)
from naru_ai.llm.prompt import NoticeEnvelope

KST = timezone(timedelta(hours=9))
TILDE = chr(0x223C)  # TOPIS 가 쓰는 물결 (TILDE OPERATOR, 일반 ~ 가 아니다)
TIME_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[~" + TILDE + r"-]\s*(\d{1,2}):(\d{2})")
TOPIS_AT = re.compile(r"(발생일시|완료예정)\s*(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})")
HINT = re.compile(r"<([^>]+)>")
PAREN = re.compile(r"\([^)]*\)")
ALIASES = {  # 규칙서 §1.1 표기 사전
    "종로1R": "종로1가사거리",
    "숭례문R": "숭례문오거리",
    "내자R": "내자동사거리",
}
MOTORWAY = ("올림픽대로", "강변북로", "동부간선도로", "내부순환로", "터널", "램프", "고가", "IC")


class RuleBaseline:
    def parse(self, env: NoticeEnvelope) -> NoticeOutput:
        text = env.text
        window, time_span = self._window(text, env)
        hints = [h.strip() for m in HINT.findall(text) for h in m.replace(" 등", "").split("·")]
        place = text.split("|")[1] if "|" in text else text
        place = HINT.sub("", PAREN.sub("", place)).strip()
        place = TIME_RANGE.sub("", place).strip(" ,")
        kind, impact, reason = self._classify(text, place)
        segments, points = self._places(place, kind)
        if not segments and not points and kind in ("march", "rally_stretch"):
            kind = "unknown"
        spans = list(time_span)
        names = [n for s in segments for n in (s.from_, *s.via, s.to)] + [p.name for p in points]
        for name in names:
            raw = next((k for k, v in ALIASES.items() if v == name), name.replace("번출구", "出"))
            if raw in text:
                spans.append(Span(text=raw, tag="POI", canonical=name))
        for h in hints:
            if h in text:
                tag = "ROAD" if h.endswith(("로", "길")) else "AREA"
                spans.append(Span(text=h, tag=tag, canonical=h))
        item = NoticeItem(
            window=window,
            approx=False,
            kind=kind,
            impact=impact,
            impact_reason=reason,
            segments=segments,
            points=points,
            toward=None,
            road_hints=hints,
            reported_people=None,
            police_stations=[],
            spans=spans,
            confidence=self._confidence(env.source, kind, impact, hints, window),
            notes=None,
        )
        return NoticeOutput(items=[item])

    # --- 시간 ---------------------------------------------------------------------
    @staticmethod
    def _window(text: str, env: NoticeEnvelope) -> tuple[Window, list[Span]]:
        year = datetime.fromisoformat(env.published_at).year
        found: dict[str, tuple[int, int, int, int]] = {}
        for k, mo, d, h, mi in TOPIS_AT.findall(text):
            found[k] = (int(mo), int(d), int(h), int(mi))
        if "발생일시" in found:
            mo, d, h, mi = found["발생일시"]
            start = datetime(year, mo, d, h, mi, tzinfo=KST)
            end = None
            if "완료예정" in found:
                mo, d, h, mi = found["완료예정"]
                end = datetime(year, mo, d, h, mi, tzinfo=KST)
            return Window(start=start.isoformat(), end=end.isoformat() if end else None), []
        m = TIME_RANGE.search(text)
        if m is None:
            return Window(start=None, end=None), []
        if env.event_date:
            day = date.fromisoformat(env.event_date)
        else:
            day = datetime.fromisoformat(env.published_at).date()
        start = datetime(day.year, day.month, day.day, int(m[1]), int(m[2]), tzinfo=KST)
        end = datetime(day.year, day.month, day.day, int(m[3]), int(m[4]), tzinfo=KST)
        if end < start:
            end += timedelta(days=1)
        canonical = f"{day.isoformat()}T{int(m[1]):02d}:{m[2]}/{int(m[3]):02d}:{m[4]}"
        span = Span(text=m.group(0), tag="TIME", canonical=canonical)
        return Window(start=start.isoformat(), end=end.isoformat()), [span]

    # --- 종류·impact -----------------------------------------------------------
    @staticmethod
    def _classify(text: str, place: str) -> tuple[Kind, Impact, ImpactReason | None]:
        kind: Kind
        if "마라톤" in text:
            kind = "marathon"
        elif "→" in place or "↔" in place or "행진" in text:
            kind = "march"
        elif "~" in place or TILDE in place:
            kind = "rally_stretch"
        elif "통제" in text:
            kind = "closure"
        elif place:
            kind = "rally_point"
        else:
            kind = "unknown"
        if "인도" in place or "광장" in place:
            return kind, "none", "sidewalk"
        if any(w in text for w in MOTORWAY):
            return kind, "none", "motorway"
        if "차 없는" in text:
            return kind, "none", "car_free"
        if "해제" in text or "정상 소통" in text:
            return kind, "none", "released"
        vehicle = any(w in text for w in ("가변차로", "무정차", "우회"))
        if vehicle and kind in ("rally_point", "unknown"):
            return kind, "none", "vehicle_measure"
        if "배치" in text and kind in ("rally_point", "unknown"):
            return kind, "none", "info_only"
        if kind == "rally_point":
            return kind, "unknown", None
        return kind, "blocks", None

    # --- 장소 ---------------------------------------------------------------------
    @classmethod
    def _places(cls, place: str, kind: Kind) -> tuple[list[Segment], list[Point]]:
        if not place:
            return [], []
        if kind in ("rally_point", "unknown"):
            return [], [Point(name=cls._name(place), road_hint=None)]
        segments: list[Segment] = []
        for part in re.split(r"\s*(?:,|/)\s*", place):
            both = "↔" in part
            chain = [cls._name(p) for p in re.split(r"\s*[→↔]\s*", part) if p.strip()]
            if not chain:
                continue
            if "~" in chain[0] or TILDE in chain[0]:
                a, b = re.split(r"\s*[~" + TILDE + r"]\s*", chain[0], maxsplit=1)
                segments.append(cls._segment(cls._name(a), cls._name(b), [], False))
                chain[0] = cls._name(b)
            if len(chain) >= 2:
                segments.append(cls._segment(chain[0], chain[-1], chain[1:-1], both))
        return segments, []

    @staticmethod
    def _segment(a: str, b: str, via: list[str], both: bool) -> Segment:
        return Segment(
            order=None,
            **{"from": a},
            to=b,
            via=via,
            road=None,
            direction="both" if both else "one_way",
            lanes=Lanes(count=None, scope=None),
            length_km=None,
        )

    @staticmethod
    def _name(raw: str) -> str:
        name = raw.strip(" ,")
        name = ALIASES.get(name, name)
        name = re.sub(r"(\d+)出", r"\1번출구", name)
        return re.sub(r"(?<=\S)R$", "사거리", name)

    @staticmethod
    def _confidence(
        source: str, kind: Kind, impact: Impact, hints: list[str], window: Window
    ) -> float:
        if impact == "none":
            return 0.0
        if impact == "unknown":
            return 0.45
        if source.startswith("topis"):
            conf = 0.8
        elif kind == "march":
            conf = 0.85 if hints else 0.75
        else:
            conf = 0.75
        if window.end is None:
            conf -= 0.15
        return round(max(conf, 0.0), 2)
