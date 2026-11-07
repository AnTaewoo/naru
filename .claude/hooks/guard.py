#!/usr/bin/env python3
"""PreToolUse hook — .claude/CLAUDE.md §2(실데이터), §5(하네스 규칙)를 강제한다.

막는 것 (exit 2 → 호출 취소, stderr가 Claude에게 간다):
  1. Write로 새 .md를 harness/·docs/decisions/·packages/fe/ 밖에 만드는 것 (하네스 문서는 harness/ 안)
  2. data/raw·data/recorded를 파일 도구나 Bash(리다이렉션·sed -i·python -c 쓰기)로 고치는 것
     — 수집·기록 CLI(make fetch / make record / scripts/*.py)는 예외
  3. 코드 변경과 하네스 변경(.claude/, harness/)이 한 커밋에 섞이는 것 — 첫 커밋은 예외
  4. main 브랜치에서 git commit / git push — 작업은 develop, main은 PR로만 (§5.1)

이 파일은 .claude/settings.json이 Claude의 Edit을 막는다. 바꾸려면 태우가 직접.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# 태우가 바꿀 수 있음
MD_ALLOWED_PREFIXES = ("harness/", "docs/decisions/", "packages/fe/", "docs/data/", "packages/ai/naru_ai/llm/prompts/")
HARNESS_PREFIXES = (".claude/", "harness/")
DATA_RE = re.compile(r"(^|[\s'\"/])data/(raw|recorded)/")
DATA_WRITE_CMD = re.compile(r"(>|>>|\btee\b|\bsed\s+-i|\bperl\s+-pi|\bcp\b|\bmv\b|\brm\b|\btruncate\b|open\([^)]*['\"]w)")
DATA_OK_CMD = re.compile(r"^\s*(make\s+(fetch|record|setup)\b|uv\s+run\s+(python\s+)?scripts/|python3?\s+scripts/|git\s|ls\b|cat\b|head\b|tail\b|wc\b|jq\b|sha256sum\b)")


def block(msg: str) -> None:
    print(f"[guard] {msg}", file=sys.stderr)
    sys.exit(2)


def rel_to_project(path: str, root: Path) -> str | None:
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def check_file_tool(tool: str, inp: dict, root: Path) -> None:
    raw = inp.get("file_path") or inp.get("notebook_path") or ""
    rel = rel_to_project(raw, root)
    if rel is None:
        return
    if rel.startswith(("data/raw/", "data/recorded/")):
        block(f"실데이터 수정: {rel} — data/raw·recorded는 수집·기록 CLI만 쓴다 (.claude/CLAUDE.md §2)")
    is_new = not (root / rel).exists()
    if tool == "Write" and is_new and rel.endswith(".md") and not rel.startswith(MD_ALLOWED_PREFIXES):
        block(
            f"새 문서 {rel} — 하네스 문서는 harness/ 안에 만든다 (.claude/CLAUDE.md §5.1). "
            f"허용 위치: {', '.join(MD_ALLOWED_PREFIXES)}. 프로젝트 문서가 꼭 필요하면 태우에게 먼저 묻는다"
        )


def staged_files(root: Path, include_worktree: bool) -> list[str]:
    def run(*args: str) -> list[str]:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        return [x for x in out.stdout.splitlines() if x] if out.returncode == 0 else []

    files = set(run("diff", "--cached", "--name-only"))
    if include_worktree:
        files |= set(run("diff", "--name-only"))
    return sorted(files)


def current_branch(root: Path) -> str:
    r = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def has_head(root: Path) -> bool:
    r = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture_output=True)
    return r.returncode == 0


def check_bash(inp: dict, root: Path) -> None:
    cmd = inp.get("command", "")
    if DATA_RE.search(cmd) and DATA_WRITE_CMD.search(cmd) and not DATA_OK_CMD.search(cmd):
        block("data/raw·data/recorded를 명령으로 고치려 한다 — 수집·기록 CLI(make fetch / make record)만 쓴다 (.claude/CLAUDE.md §2)")
    if re.search(r"\bgit\s+(commit|push)\b", cmd) and current_branch(root) in ("main", "master"):
        block("main 브랜치다 — 작업은 develop에서 한다 (.claude/CLAUDE.md §5.1). `git switch develop` 먼저")
    if re.search(r"\bgit\s+(checkout|switch)\s+(-b|-c)\b", cmd):
        block("새 브랜치를 만들지 않는다 — develop에 직접 커밋한다 (.claude/CLAUDE.md §5.1)")
    if re.search(r"\bgit\s+commit\b", cmd) and has_head(root):
        all_flag = bool(re.search(r"\s(--all|-[a-zA-Z]*a[a-zA-Z]*)\b", cmd))
        files = staged_files(root, include_worktree=all_flag)
        harness = [f for f in files if f.startswith(HARNESS_PREFIXES)]
        code = [f for f in files if not f.startswith(HARNESS_PREFIXES)]
        if harness and code:
            block(
                "코드와 하네스 변경이 한 커밋에 섞였다 (.claude/CLAUDE.md §5.2). 나눠서 커밋한다.\n"
                f"  하네스: {', '.join(harness)}\n  코드: {', '.join(code)}"
            )


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".")
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        check_file_tool(tool, inp, root)
    elif tool == "Bash":
        check_bash(inp, root)


if __name__ == "__main__":
    main()
