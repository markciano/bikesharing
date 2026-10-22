#!/usr/bin/env bash
# Lints docs/**/*.md. Single entry point, locally and in the CI job `docs`: bash scripts/lint-docs.sh
# Runs only the markdownlint-cli2 version locked in package-lock.json (installed with `npm ci`); never downloads one.
set -euo pipefail

cd "$(dirname "$0")/.."

# With the exact pin in package.json, `npm ls` fails if the package is missing or at another version.
if ! npm ls --depth=0 markdownlint-cli2 >/dev/null 2>&1; then
  echo "markdownlint-cli2 is not installed at the locked version. Run \`npm ci\` first." >&2
  exit 1
fi

npx --no markdownlint-cli2 "docs/**/*.md"
