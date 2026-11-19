#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): formats and lints the edited .py file under pipeline/ with ruff,
# through the pipeline's locked environment. Silent when the file is clean or out of scope;
# otherwise sends what remains to Claude (exit 2).
set -uo pipefail

cd "$CLAUDE_PROJECT_DIR"

# Hooks inherit the PATH of the process that launched claude; without node or uv every edit would pass unlinted.
for tool in node uv; do
  if ! command -v "$tool" >/dev/null; then
    echo "$tool not on PATH; launch claude from a shell that has it" >&2
    exit 1
  fi
done

# The hook input is JSON on stdin; node is pinned in .nvmrc, so no extra tool is needed to parse it.
file=$(node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>process.stdout.write(JSON.parse(d).tool_input?.file_path??""))')
[[ "$file" == "$CLAUDE_PROJECT_DIR"/pipeline/*.py && -f "$file" ]] || exit 0

# A file ruff cannot format, such as one with a syntax error, is reported before linting.
if ! out=$(uv run --quiet --project pipeline ruff format "$file" 2>&1); then
  echo "$out" >&2
  exit 2
fi

out=$(uv run --quiet --project pipeline ruff check --fix "$file" 2>&1) && exit 0
echo "$out" >&2
exit 2
