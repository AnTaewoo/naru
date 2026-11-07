#!/usr/bin/env bash
# 가짜 데이터·모킹 금지어 검사. .claude/CLAUDE.md §2, .claude/skills/real-data-testing/SKILL.md §5
set -euo pipefail
cd "$(dirname "$0")/../.."

PATTERNS='unittest\.mock|MagicMock|monkeypatch|\brespx\b|import responses|from responses|import vcr|httpretty|\bfaker\b|Faker\(|\bmsw\b|vi\.fn|vi\.spyOn|jest\.|\bnock\b|\bsinon\b|test\.skip|it\.skip|describe\.skip|\bfake|\bdummy|\bstub|\bmock|sample_|pytest\.skip|mark\.skip|xfail'
TARGETS="packages scripts"

hits=$(grep -rnEi --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js' --include='*.mjs' --include='*.json' \
  --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=dist \
  "$PATTERNS" $TARGETS 2>/dev/null || true)

# 파일명 검사
names=$(find $TARGETS -type f \( -iname '*fake*' -o -iname '*dummy*' -o -iname '*stub*' -o -iname '*mock*' -o -iname 'sample_*' \) \
  -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -name 'check_no_fakes.sh' 2>/dev/null || true)

if [[ -n "$hits" || -n "$names" ]]; then
  echo "❌ check-no-fakes 실패 — 가짜 데이터/모킹 금지 (.claude/CLAUDE.md §2)"
  [[ -n "$hits" ]] && { echo "--- 내용 ---"; echo "$hits"; }
  [[ -n "$names" ]] && { echo "--- 파일명 ---"; echo "$names"; }
  echo "실데이터로 바꾸거나, 왜 안 되는지 태우에게 설명한다. 우회 금지."
  exit 1
fi
echo "✅ check-no-fakes 통과"
