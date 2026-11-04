#!/usr/bin/env bash
# 가짜·합성 데이터, 모킹, 테스트 건너뛰기 금지어 검사. CLAUDE.md §2.2, real-data-testing §7
# 이 파일은 .claude/settings.json이 Claude의 Edit을 막는다. 바꾸려면 태우가 직접.
set -euo pipefail
cd "$(dirname "$0")/.."

# 대소문자 무시. 모킹 | 가짜 | 건너뛰기 | 합성·증강
PATTERNS='unittest\.mock|MagicMock|monkeypatch|\brespx\b|import responses|from responses|import vcr|httpretty|\bfaker\b|Faker\(|\bfake|\bdummy|\bstub|\bmock|pytest\.skip|mark\.skip|xfail|\bsynthetic|\baugment|paraphras|back_?translat'
TARGETS="src tests configs labeling scripts"

hits=$(grep -rnEi \
  --include='*.py' --include='*.pyi' --include='*.yaml' --include='*.yml' --include='*.toml' \
  --include='*.json' --include='*.jsonl' --include='*.xml' --include='*.cfg' --include='*.ini' \
  --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=ls-data --exclude-dir=format_probe \
  "$PATTERNS" $TARGETS 2>/dev/null || true)

# 파일명 검사 (이 스크립트 자신은 제외)
names=$(find $TARGETS -type f \
  \( -iname '*fake*' -o -iname '*dummy*' -o -iname '*stub*' -o -iname '*mock*' \
     -o -iname '*synthetic*' -o -iname '*augment*' \) \
  -not -path '*/.venv/*' -not -path '*/ls-data/*' -not -name 'check_no_fakes.sh' 2>/dev/null || true)

if [[ -n "$hits" || -n "$names" ]]; then
  echo "❌ check-no-fakes 실패 — 가짜·합성 데이터, 모킹, 건너뛰기 금지 (CLAUDE.md §2.2)"
  [[ -n "$hits" ]] && { echo "--- 내용 ---"; echo "$hits"; }
  [[ -n "$names" ]] && { echo "--- 파일명 ---"; echo "$names"; }
  echo "실데이터로 바꾸거나, 왜 안 되는지 태우에게 설명한다. 철자를 바꿔 피하지 않는다."
  exit 1
fi
echo "✅ check-no-fakes 통과"
