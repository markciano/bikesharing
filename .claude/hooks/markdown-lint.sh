#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): fixes and lints the Markdown scope set in .markdownlint-cli2.yaml.
# Silent when the edited file is clean or out of scope; otherwise sends its remaining errors to Claude (exit 2).
set -uo pipefail

cd "$CLAUDE_PROJECT_DIR"

# Hooks inherit the PATH of the process that launched claude; without node every edit would pass unlinted.
if ! command -v node >/dev/null; then
  echo "node not on PATH; launch claude from a shell with fnm loaded" >&2
  exit 1
fi

# The hook input is JSON on stdin; node is pinned in .nvmrc, so no extra tool is needed to parse it.
file=$(node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>process.stdout.write(JSON.parse(d).tool_input?.file_path??""))')
[[ "$file" == *.md ]] || exit 0
rel="${file#"$CLAUDE_PROJECT_DIR"/}"

# The whole scope is fixed and linted (under a second): a path passed explicitly would bypass the scope.
out=$(bash scripts/lint-docs.sh --fix 2>&1) && exit 0

errors=$(grep -F -- "$rel:" <<<"$out" | grep -v '^Finding:')
if [[ -n "$errors" ]]; then
  echo "$errors" >&2
  exit 2
fi

# Errors only in other files are not this edit's; a missing install is shown to the owner.
if grep -q 'npm ci' <<<"$out"; then
  echo "$out" >&2
  exit 1
fi
exit 0
