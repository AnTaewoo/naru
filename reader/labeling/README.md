# 라벨링 운영

## 1. 기동 (R0.4)
1. `.env`의 `LABEL_STUDIO_VERSION`에 Docker Hub `heartexlabs/label-studio`의 태그 하나를 고정한다 (latest 금지 — 비어 있으면 compose가 멈춘다)
2. `make ls-up` → `http://<서버>:8080`
3. 첫 계정 = 태우(관리자). 그다음 `docker-compose.yml`의 가입 차단 줄 주석을 풀고 `make ls-down && make ls-up`. 팀원은 초대 링크로 가입
4. 프로젝트 생성 → Labeling Setup → Code → `label_config.xml` 내용을 붙여넣는다
5. 토큰 → `.env`의 `LABEL_STUDIO_API_KEY`
6. 팀원이 밖에서 접속해야 하면 Tailscale 같은 사설망을 쓴다. 8080을 인터넷에 직접 열지 않는다
7. 볼륨 권한 오류가 나면 설치한 버전의 문서에서 컨테이너 사용자 UID를 확인한다

## 2. 실제 export 구조 (R0.4에서 채운다 — `format_probe/`의 파일을 열어 확인한 것만)
- 파일: `labeling/format_probe/<ts>.json`
- 스팬 region 경로:
- offset 기준 (`text[start:end]`가 맞는지):
- 정규형(TextArea) ↔ 스팬 region 연결 방식:
- 주석자 식별 필드 (id인지 이메일인지, id면 이메일로 바꾸는 방법):
- `quality` Choices 경로:
- 사전 주석(predictions)을 import할 때의 형식 (R3.2에서 이 구조를 거꾸로 쓴다):

## 3. 프로젝트 구성 (R3.2에서 결정)
- 파일럿(R3.1): 20문장, 태우 + 1명이 각자
- 본 라벨: 500문장. 교차 50은 두 사람이 각자 단다
- 사전 주석은 train 기간 문장에만 들어간다. val·test·test_ood는 빈 화면

## 4. 라벨링 중
- 가이드는 `docs/labeling_guide.md`의 확정본(v1 이상)만
- 교차로·도로 정규형은 `data/gazetteer/browse.html`에서 복사한다
- 기사 원문을 찾아 읽지 않는다. 화면에 보이는 문장·앞뒤 문장·게시 시각만 쓴다
- 막히면 최선으로 달고 `issues.md`에 sentence_id를 남긴다

## 5. 고치는 법
- 오류 발견 → `issues.md` → 담당 주석자가 Label Studio에서 수정 → `make export` → data_version 올림
- `data/labeled/`의 파일은 사람도 Claude도 직접 고치지 않는다

## 6. 백업
`labeling/ls-data/`(Label Studio DB)와 `data/labeled/`를 비공개 저장소에 주기적으로 복사한다. 라벨은 다시 만들 수 없는 유일한 데이터다.
