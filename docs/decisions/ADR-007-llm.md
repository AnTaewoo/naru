# ADR-007 공지 파서는 Claude API — 로컬 사후학습은 해커톤 이후
- 상태: 승인 (2026-11-06, 태우)
- 개정 대상: ADR-006의 "LLM 보류" 행

## 맥락
공지 문장에서 시간·장소·구간을 뽑는 파서가 필요하다. 선택지는 (a) Claude API few-shot 구조화 출력, (b) 로컬 소형 모델 사후학습(klue/roberta-base 미세조정, KLUE NER 전이, 로컬 LLM LoRA). 해커톤 최종 제출이 2026-11-16이고 사람 라벨은 그때까지 200~300문장이 한계다.

## 결정
1. **해커톤 범위에서 공지 파서는 Claude API** (`claude-haiku-5-5` 기본, `claude-sonnet-5-5`는 비교용). tool use로 출력 스키마를 고정한다.
2. 출력은 **spans + segments**. segments(from/to/via/road/window)를 모델이 내고, 좌표는 지명사전 리졸버가, 선은 BE 도로 그래프가 만든다. 모델이 만든 좌표는 계약에 들어올 수 없다.
3. 모든 응답을 `data/recorded/llm/`에 기록하고 테스트·시연은 재생한다. 당일 API 장애와 무관하다.
4. 로컬 사후학습은 **해커톤 이후** 별도 저장소 `naru-reader`의 실측(정규형 F1 차이의 95% 신뢰구간, 허용폭 0.05)으로 판단한다. 동급이면 두 번째 클라이언트로 추가하고 이 ADR을 개정한다.

## 이유
- 구현이 프롬프트 + 정렬기로 끝난다. 학습 루프·토크나이저 정렬·디코더가 없다. 11일 안에 "AI가 필요한가"의 숫자(규칙 기준선 vs 모델)를 내는 데 시간을 쓸 수 있다.
- 라벨은 평가에만 쓰면 된다. 200~300문장이면 충분하다.
- 비용은 월 $1 미만(공지 50건/일). 지연 1~5초는 5분 폴링에서 체감되지 않는다.
- 관계 추출(구간)은 토큰 분류 모델엔 추가 학습이 필요하지만 API는 스키마에 칸 하나면 된다. 구간이 집회 행진의 핵심이다.

## 결과 — 이 선택 때문에 바뀌는 것
- `LLMClient` Protocol·`KananaClient`·T5.6을 지운다. 클라이언트는 `AnthropicClient` 하나.
- `NoticeClassifier`(121곳 zone 분류)가 `NoticeParser`(spans + segments)로 바뀐다. `ZoneMatcher`는 지역명 공지에만 쓰고 v1로 미룬다.
- INTERFACE v0.5: `SegmentGeom`·`PlacePoint`·`NoticeRef` 추가. BE `CrosswalkIndex.from_segment` + `RoadGraph` + 도로 등급별 버퍼 추가 (T1.2).
- 외부 의존이 생긴다. 공지 문장은 공개 정보라 반출 문제는 없다. 온프레미스(B2B, ADR-004)가 필요해지면 로컬 전환 실측의 이유가 된다.

## 측정 (T4.3)
규칙 기준선(지명사전·정규식) vs Claude: val 정규형 F1, 구간 F1, 횡단보도 집합 Jaccard. 숫자는 보고서 2.3 "AI가 필요한 이유"에 들어간다.
