"""BE 설정 — 임계값과 경로는 전부 여기 (CONVENTIONS §1 "설정"). os.environ을 직접 읽지 않는다.

INTERFACE §5 / ARCHITECTURE 상태기계 표의 숫자(0.7, 0.8, x3, 30분), CrosswalkIndex 반경·버퍼,
PedGraph 조립 임계값. 바꾸면 그 문서들도 같이 바꾼다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NARU_", extra="ignore")

    data_dir: Path = Path("data")
    districts: tuple[str, ...] = ("종로구", "중구")  # 데모 범위 (광화문 일대)

    # DB (.env DATABASE_URL / TEST_DATABASE_URL — 접두사 없음, docker compose MySQL 8.4 호스트 3307)
    database_url: str = Field(
        default="mysql+pymysql://naru:naru@localhost:3307/naru", validation_alias="DATABASE_URL"
    )
    test_database_url: str = Field(
        default="mysql+pymysql://naru:naru@localhost:3307/naru_test",
        validation_alias="TEST_DATABASE_URL",
    )

    # POST /internal/candidates 헤더 X-Naru-Internal-Token (.env NARU_INTERNAL_TOKEN). 비면 전부 401
    internal_token: str = ""

    # 지오코딩 (ADR-011 B, INTERFACE §7) — 카카오 로컬. 키는 .env KAKAO_REST_KEY(접두사 없음),
    # 서버에만.
    # recorded = data/recorded/kakao/local 재생(테스트·e2e·기록), live = 실서버
    kakao_rest_key: SecretStr = Field(default=SecretStr(""), validation_alias="KAKAO_REST_KEY")
    geocode_source: Literal["live", "recorded"] = "live"
    kakao_timeout_s: float = 5.0

    # 상태기계 (ARCHITECTURE "ClosureState 상태기계", INTERFACE §5)
    review_confidence: float = 0.7  # 미만이면 review_required, 라우팅에 안 씀
    confirmed_confidence: float = 0.8
    # ADR-011 A — 예정(확신도 ≥ review_confidence)은 횡단보도에 닿는 시각이 공지 창 안일 때만
    # 횡단보도당 +300초(비용은 m 라 walk_speed 로 환산). 창 밖은 보통 간선. 하드 차단은 confirmed 만
    scheduled_penalty_s: float = 300.0
    # ADR-011 그래프 밖 — 출발·도착을 보행망에 붙일 거리 상한, 넘으면 out_of_coverage
    max_snap_m: float = 150.0
    released_grace_min: int = 30  # 시각표 종료 + 30분 → released
    unknown_end_hours: int = 6  # window.end 없으면 시작 + 6시간을 임시 end 로 (INTERFACE §1)
    # ADR-008: unknown 지점이 도로 30 m 안이면 blocks 승격(CandidateIntake). toward 선 확신 상한
    unknown_impact_road_m: float = 30.0
    toward_confidence_cap: float = 0.65

    # 라우터 (T3.1): 보행 속도, 수직 이동 패널티(연결 간선 길이에 더하는 m)
    walk_speed_mps: float = 1.2
    stairs_penalty_m: float = 25.0
    elevator_penalty_m: float = 40.0
    # 폐쇄 조회 범위: route bbox 여유 m, 기준 시각 뒤 이 시간 안에 시작하는 것도 (route·closures)
    route_bbox_pad_m: float = 1000.0
    route_horizon_min: int = 60

    # CrosswalkIndex (T1.2)
    point_radius_m: float = 30.0
    line_buffer_m: float = 15.0
    road_buffer_m: dict[str, float] = Field(
        default_factory=lambda: {"대로": 25.0, "로": 15.0, "길": 8.0}
    )

    # PedGraph 조립 (T1.1). 지하도 출입구의 93%가 도보망 노드 30 m 안
    crosswalk_match_m: float = 15.0  # 관리번호 점 → 횡단보도 간선
    crosswalk_attach_any_m: float = 8.0  # 없으면 아무 간선 (점은 간선 위, 중앙값 1.8 m)
    crosswalk_promote_max_m: float = 60.0  # 그 간선이 이보다 짧으면 kind를 crosswalk으로
    connector_max_m: float = 30.0
    # 경로 상세(T5.10) — 관리번호 없는 횡단보도 간선은 이 안의 가장 가까운 도로명으로 이름을 단다
    crosswalk_road_name_m: float = 20.0
