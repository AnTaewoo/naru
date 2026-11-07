"""공지 파서 출력 스키마 — 규칙서 v2 §2·§9.1 (docs/data/notice_parser_rules_v2.md). 좌표 칸 없음.

pydantic 모델이 진실이고, Claude tool use 의 strict input_schema 는 여기서 생성한다
(additionalProperties false · 모든 필드 required · $defs 인라인). 시각은 문자열(ISO 8601 +09:00)
그대로 받는다 — datetime 변환·정렬기는 notice/parser.py(T4.2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["march", "rally_point", "rally_stretch", "closure", "marathon", "unknown"]
Impact = Literal["blocks", "none", "unknown"]
ImpactReason = Literal[
    "motorway", "car_free", "sidewalk", "vehicle_measure", "released", "info_only", "unconfirmed"
]
Tag = Literal["TIME", "ROAD", "INTERSECTION", "POI", "ADDRESS", "AREA"]
Direction = Literal["one_way", "both"]
LaneScope = Literal["partial", "full", "one_side_full"]

TOOL_NAME = "parse_notice"
TOOL_DESCRIPTION = (
    "통제 공지 한 건을 구조화한다. 공지에 적힌 시간 구간·장소 이름(점 또는 구간)·종류·횡단보도 "
    "통행을 막는 재료인지(impact)를 규칙서대로 낸다. 좌표·주소·횡단보도 ID 는 내지 않는다. "
    "모르면 null."
)


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: str | None = Field(description="ISO 8601 +09:00. 없으면 null")
    end: str | None = Field(description="ISO 8601 +09:00. 끝이 없으면 null")


class Lanes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int | None
    scope: LaneScope | None


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    order: int | None = Field(description="※①②③ 번호. 없으면 null")
    from_: str = Field(alias="from", description="정규 이름 또는 원문")
    to: str
    via: list[str]
    road: str | None = Field(description="문장이 이 구간의 도로를 명시할 때만")
    direction: Direction
    lanes: Lanes
    length_km: float | None


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    road_hint: str | None


class Span(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="문장 안 표현 그대로")
    tag: Tag
    canonical: str


class NoticeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window: Window
    approx: bool
    kind: Kind
    impact: Impact
    impact_reason: ImpactReason | None = Field(description="impact 가 none 일 때 이유")
    segments: list[Segment]
    points: list[Point]
    toward: str | None = Field(description="종료 지점 없는 행진의 방향 표현, 문장 그대로")
    road_hints: list[str]
    reported_people: int | None
    police_stations: list[str]
    spans: list[Span]
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None


class NoticeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[NoticeItem]


def strict_input_schema() -> dict[str, object]:
    """NoticeOutput → Claude strict tool input_schema (참조 인라인, 전부 required, 추가 필드 X)."""
    raw = NoticeOutput.model_json_schema(by_alias=True)
    defs: dict[str, object] = dict(raw.pop("$defs", {}))

    def walk(node: object) -> object:
        if isinstance(node, dict):
            if "$ref" in node:
                name = str(node["$ref"]).rsplit("/", 1)[-1]
                return walk(defs[name])
            out: dict[str, object] = {}
            for key, value in node.items():
                # API 가 number 의 minimum/maximum 을 거부한다 (2026-11-07, 400 "properties maximum,
                # minimum are not supported"). 범위 검증은 pydantic(ge/le)이 재생 때 한다
                if key in ("title", "default", "minimum", "maximum"):
                    continue
                out[key] = walk(value)
            if out.get("type") == "object" and isinstance(out.get("properties"), dict):
                props = out["properties"]
                assert isinstance(props, dict)
                out["required"] = list(props)
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    schema = walk(raw)
    assert isinstance(schema, dict)
    return schema
