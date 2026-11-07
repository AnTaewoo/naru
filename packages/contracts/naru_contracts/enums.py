"""enum 코드값 — 영어 snake_case. 한국어 라벨은 FE i18n/ko.ts에만 (INTERFACE §4)."""

from enum import StrEnum


class Status(StrEnum):
    scheduled = "scheduled"
    confirmed = "confirmed"
    released = "released"
    zone_scheduled = "zone_scheduled"


class Source(StrEnum):
    course = "course"
    smpa = "smpa"
    topis = "topis"
    news = "news"
    seoul_press = "seoul_press"
    incident = "incident"
    bus = "bus"
    rtd = "rtd"


class ClosureType(StrEnum):
    marathon = "marathon"
    march = "march"
    rally = "rally"
    event = "event"
    incident = "incident"


class GeometryKind(StrEnum):
    point = "point"
    line = "line"
    segment = "segment"
    zone = "zone"


class RoadClass(StrEnum):
    """도로명 접미사. BE가 버퍼 폭을 고른다 (대로 25m / 로 15m / 길 8m — naru_be/config.py)."""

    daero = "대로"
    ro = "로"
    gil = "길"


class EvidenceKind(StrEnum):
    notice = "notice"
    timetable = "timetable"
    topis_incident = "topis_incident"
    bus_skip = "bus_skip"
    bus_return = "bus_return"
    rtd_spike = "rtd_spike"


class LegKind(StrEnum):
    sidewalk = "sidewalk"
    crosswalk = "crosswalk"
    underpass = "underpass"
    overpass = "overpass"
    stairs = "stairs"
    elevator = "elevator"
    station = "station"
