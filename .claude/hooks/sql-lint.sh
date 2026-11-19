#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): fixes and lints the edited .sql file under pipeline/dbt/ with SQLFluff,
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
[[ "$file" == "$CLAUDE_PROJECT_DIR"/pipeline/dbt/*.sql && -f "$file" ]] || exit 0

# SQLFluff's dbt templater loads dbt's profile, which reads its paths and memory limit from these
# variables; a throwaway folder stands in for the run's work folder, as in check-pipeline.sh.
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export BIKESHARING_ALLOWED_DIRECTORY="$work"
export BIKESHARING_SCRATCH_DATABASE="$work/scratch.duckdb"
export BIKESHARING_TEMP_DIRECTORY="$work/spill"
export BIKESHARING_MEMORY_LIMIT="1GiB"

# What fix leaves behind is what lint reports, so fix's own output is not needed.
uv run --quiet --project pipeline sqlfluff fix "$file" >/dev/null 2>&1
out=$(uv run --quiet --project pipeline sqlfluff lint "$file" 2>&1) && exit 0
echo "$out" >&2
exit 2
