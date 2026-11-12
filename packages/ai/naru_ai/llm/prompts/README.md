# 프롬프트 버전
- `notice_v1.md` — T4.1에서 만든다. 바꾸면 `notice_v2.md`로 새 파일. 기록된 응답(`data/recorded/llm/anthropic/<model>@api/<prompt_version>/`)은 프롬프트 버전별로 따로 둔다.
- 구조: 지시문(태그 5종·구간 규칙·경계 규칙) + few-shot(실제 공지 문장·정답, `data/raw/notices/`에서 고른 id 명시) + 입력(문장·앞뒤 문장·published_at).
- 출력은 tool use `input_schema`로 고정: `spans[{text, tag, canonical}]`, `segments[{road, from, to, via, window, kind, scope}]`.
