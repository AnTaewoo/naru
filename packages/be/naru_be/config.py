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
    # 서비스 범위 = 서울 25개 구 전부 (태우 2026-11-09, T6.9). 이름은 OA-23081 자치구 열 그대로
    districts: tuple[str, ...] = (
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
        "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
        "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구",
    )  # fmt: skip

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
    # 행진 확률 모델 (ADR-015 가정값 표, T7.16) — 근거 없는 값은 11/14 현장 검증 뒤 다시 정한다
    march_samples: int = 21  # 속도 표본 수 (u = -1, -0.9 … 1)
    # ±50% 면 긴 행진(국회대로 9.5 km)에서 P 가 전부 하한으로 눌려(11/10 기록) ±20% (태우 11/10 ①)
    march_speed_spread: float = 0.2  # v_i = v(1 ± 0.2u)
    march_lead_m: float = 300.0  # 행렬 앞에서 미리 막는 거리
    march_queue_m: float = 200.0  # 인원을 모를 때 행렬 길이
    march_queue_min_m: float = 100.0  # 인원이 적어도 이보다 짧게 보지 않는다
    march_density: float = 2.0  # 명/m²
    lane_width_m: float = 3.5  # 차로 폭 — 공지 lanes.count 가 후보에 있을 때(지금은 없다)
    march_width_m: dict[str, float] = Field(
        default_factory=lambda: {"대로": 16.0, "로": 10.0, "길": 6.0}
    )
    march_p_floor: float = 0.2  # 공지 창 안 경로 위 최저 P
    march_p_floor_confirmed: float = 0.5  # 통제 중(돌발이 붙은) 행진의 최저 P (태우 11/10 ③)
    march_p_block: float = 0.8  # 이 이상이면 간선 제외 (confirmed_confidence 와 같은 값)
    march_join_m: float = 50.0  # 앞 구간 끝·다음 시작 사이 이 안이면 이어진 경로
    march_keyframe_s: int = 60  # 키프레임 간격 (태우 1분)
    march_point_step_m: float = 25.0  # 표본마다 머리~꼬리 점 간격
    march_points_max: int = 600  # 키프레임당 점 상한
    # 알림 (ADR-014 C, T7.8) — VAPID 키는 .env 의 태우 것(NARU_VAPID_PRIVATE_KEY PEM 또는 raw,
    # NARU_VAPID_SUBJECT mailto:). 없으면 /push/vapid-public-key 가 503
    vapid_private_key: SecretStr = SecretStr("")
    vapid_subject: str = ""
    watch_saved_max: int = 10  # 구독당 저장 관심 지역 수
    watch_last_seen_grid_m: float = 150.0  # 마지막 위치는 이 격자로 반올림 (개인정보)
    watch_last_seen_ttl_h: int = 3  # 마지막 위치는 이 시간 뒤 삭제
    # 공개 피드 (T7.17, INTERFACE §3.3) — 분 단위 캐시, IP 당 분당 요청 상한 (gunicorn 워커마다)
    feed_cache_s: int = 60
    feed_cache_max: int = 64
    feed_rate_per_min: int = 60
    # 통제 제보 (T7.15, INTERFACE §8) — 가정값, 11/14 현장 검증 뒤 다시 정한다
    report_snap_m: float = 100.0  # 지금 위치 → 가장 가까운 횡단보도 상한
    report_min_interval_s: int = 600  # 같은 기기·같은 횡단보도 다시 제보 간격
