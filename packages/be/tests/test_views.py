"""T3.3 — View: 실데이터 Model 출력 → render → 응답이 contracts 로 model_validate 되는지, +09:00.

RouteResult 는 T3.1·T3.2 라우터를 코스 후보 상태로 돌린 실제 결과(교보빌딩 → 대한문 07:45).
jsonify 는 앱 컨텍스트가 필요해 맨 Flask 앱을 하나 띄운다 (create_app 은 T3.4).
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone

import pytest
from conftest import CourseWorld
from flask import Flask
from pydantic import ValidationError

from naru_be.errors import InvalidQueryError, NoRouteError
from naru_be.models.domain.route_planner import parse_latlng
from naru_be.models.domain.routers import BaselineRouter, TimeDependentRouter
from naru_be.models.domain.types import RouteResult
from naru_be.views import closure_view, error_view, route_view
from naru_contracts import ErrorBody, FeatureCollection, RouteQuery, RouteResponse, Status

KST = timezone(timedelta(hours=9))
KYOBO = parse_latlng("37.5709686446227,126.9779039768265", "from")  # 카카오 24020019
DAEHANMUN = parse_latlng("37.5650416322942,126.976542945622", "to")  # 카카오 17582477


@pytest.fixture(scope="module", autouse=True)
def app_context() -> Iterator[None]:
    app = Flask("naru-view-test")
    with app.app_context():
        yield


@pytest.fixture(scope="module")
def result(course_world: CourseWorld) -> RouteResult:
    w = course_world
    depart = datetime(2026, 3, 15, 7, 45, tzinfo=KST)  # 1구간 07:20~08:08 통제 중
    path = TimeDependentRouter(w.ped, w.engine, w.settings).route(
        KYOBO, DAEHANMUN, depart, w.states
    )
    baseline = BaselineRouter(w.ped, w.settings).route(KYOBO, DAEHANMUN)
    assert path.avoided and path.coords != baseline.coords
    return RouteResult(path, baseline, depart, datetime(2026, 3, 15, 7, 44, 30, tzinfo=UTC))


def test_route_view_renders_interface_section_2(result: RouteResult) -> None:
    resp = route_view.render(result)
    assert resp.status_code == 200 and resp.mimetype == "application/json"
    body = RouteResponse.model_validate(resp.get_json())
    assert body.route.coordinates == list(result.path.coords)
    assert body.distance_m == result.path.distance_m and body.duration_s == result.path.duration_s
    assert [leg.kind.value for leg in body.legs] == [leg.kind.value for leg in result.path.legs]
    underpass = next(leg for leg in body.legs if leg.kind.value == "underpass")
    assert underpass.name is not None and underpass.name.endswith("지하보도")
    assert body.baseline.route.coordinates == list(result.baseline.coords)
    assert body.baseline.distance_m == result.baseline.distance_m < body.distance_m
    # 시각은 전부 +09:00 (CONVENTIONS §4.5). computed_at 은 UTC 로 줬어도 KST 로 나간다
    raw = resp.get_json()
    assert raw["computed_at"] == "2026-03-15T16:44:30+09:00"
    avoided = {a["crosswalk_id"]: a for a in raw["avoided"]}
    assert avoided["06-0000023206"]["until"] == "2026-03-15T08:08:00+09:00"
    assert avoided["06-0000023206"]["status"] == "confirmed"
    assert avoided["06-0000023206"]["approx"] is False
    assert all(ev["at"].endswith("+09:00") for a in raw["avoided"] for ev in a["evidence"])
    assert body.avoided[0].evidence[0].kind.value == "timetable"
    assert "+00:00" not in resp.get_data(as_text=True)


def test_closure_view_renders_feature_collection(course_world: CourseWorld) -> None:
    states = course_world.states
    resp = closure_view.render(states)
    assert resp.status_code == 200
    fc = FeatureCollection.model_validate(resp.get_json())
    assert len(fc.features) == len(states)
    for f, s in zip(fc.features, states, strict=True):  # 같은 횡단보도가 여러 구간에 나올 수 있다
        p = f.properties
        assert p.crosswalk_id == s.crosswalk_id and p.zone_name is None
        assert f.geometry.type == "Point" and f.geometry.coordinates == (s.lng, s.lat)
        assert p.status is Status.scheduled and p.confidence == s.confidence
        assert p.impact is s.impact and p.approx is s.approx and p.reason == s.reason
        assert p.window["start"] == s.window.start and p.window["end"] == s.window.end
        assert p.window["start"] is not None and p.window["start"].utcoffset() == timedelta(hours=9)
        assert p.evidence is not None and len(p.evidence) == len(s.evidence)
    raw = resp.get_json()
    first = next(f for f in raw["features"] if f["properties"]["crosswalk_id"] == "06-0000023206")
    assert first["properties"]["window"]["start"] == "2026-03-15T07:20:00+09:00"  # 1구간
    assert closure_view.render([]).get_json() == {"type": "FeatureCollection", "features": []}


def test_error_view_maps_codes_and_fields() -> None:
    resp, status = error_view.render(InvalidQueryError("from: 'lat,lng' 형식이어야 한다", "from"))
    assert status == 400
    body = ErrorBody.model_validate(resp.get_json())
    assert body.error.code == "invalid_query" and body.error.field == "from"
    assert body.error.message.startswith("from:")
    resp, status = error_view.render(NoRouteError("경로 없음"))
    assert status == 422 and ErrorBody.model_validate(resp.get_json()).error.code == "no_route"
    # 오프셋 없는 depart_at → pydantic ValidationError → 400 invalid_query, field=depart_at
    with pytest.raises(ValidationError) as e:
        RouteQuery.model_validate({"from": "1,2", "to": "3,4", "depart_at": "2026-03-15T07:00:00"})
    resp, status = error_view.render(e.value)
    assert status == 400
    body = ErrorBody.model_validate(resp.get_json())
    assert body.error.code == "invalid_query" and body.error.field == "depart_at"
    assert "오프셋" in body.error.message
    # 알 수 없는 필드(extra=forbid)도 invalid_query, 그 필드명
    with pytest.raises(ValidationError) as e:
        RouteQuery.model_validate(
            {"from": "1,2", "to": "3,4", "depart_at": "2026-03-15T07:00:00+09:00", "x": 1}
        )
    assert error_view.render(e.value)[0].get_json()["error"]["field"] == "x"
    resp, status = error_view.render_code("unauthorized", "X-Naru-Internal-Token 불일치", 401)
    assert status == 401 and ErrorBody.model_validate(resp.get_json()).error.field is None
