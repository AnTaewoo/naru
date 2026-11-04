# ADR-R00 스택·버전

상태: **초안** — R0.1~R0.4와 해당 Task에서 실제 설치·확인한 값을 채우고 태우 승인

## 결정
CLAUDE.md §5의 스택을 쓴다. 버전은 `uv.lock`으로 고정하고, 아래 표엔 **설치 후 확인한 값**만 적는다 (`uv pip list`, `nvidia-smi`, `docker image ls`).

| 항목 | 용도 | 버전 (실제) | 채운 Task |
|---|---|---|---|
| Python | | | R0.1 |
| uv | | | R0.1 |
| pydantic | 레코드 | | R0.1 |
| ruff · mypy · pytest · import-linter | 품질·게이트 | | R0.1 |
| GPU · 드라이버 · CUDA | | | R0.2 |
| torch (CUDA 휠 인덱스) | 학습 | | R0.2 |
| transformers · datasets · accelerate | 학습 | | R0.2 |
| httpx | 수집·API | | R0.3 |
| anthropic | exp004 | | R0.3 |
| Label Studio (docker 이미지 태그) | 라벨 | | R0.4 |
| trafilatura · 문장 분리기 | 수집 | | R1.2 |
| pdfplumber | 오늘의 집회 | | R1.3b |
| pyproj · shapely · folium | 지명사전·지도 | | R2.x |
| seqeval | 지표 대조 | | R4.0 |
| peft · 양자화 · 제약 디코딩 | exp005 | | R4.6 |

## 결과
- 버전을 올리면 이 표와 `uv.lock`을 같은 커밋에서 바꾼다
- 실험 도중(R4.2~R4.7) 버전을 올리지 않는다. 올려야 하면 이미 낸 val 숫자를 다시 낸다
