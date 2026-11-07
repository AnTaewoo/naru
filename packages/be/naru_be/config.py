"""BE 설정 — 임계값과 경로는 전부 여기 (CONVENTIONS §1 "설정"). os.environ을 직접 읽지 않는다.

INTERFACE §5 / ARCHITECTURE 상태기계 표의 숫자(0.7, 0.8, x3, 30분), CrosswalkIndex 반경·버퍼,
PedGraph 조립 임계값. 바꾸면 그 문서들도 같이 바꾼다.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NARU_", extra="ignore")

    data_dir: Path = Path("data")
    districts: tuple[str, ...] = ("종로구", "중구")  # 데모 범위 (광화문 일대)

    # 상태기계 (ARCHITECTURE "ClosureState 상태기계", INTERFACE §5)
    review_confidence: float = 0.7  # 미만이면 review_required, 라우팅에 안 씀
    confirmed_confidence: float = 0.8
    scheduled_cost_factor: float = 3.0  # scheduled 간선 비용 x3
    released_grace_min: int = 30  # 시각표 종료 + 30분 → released

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
