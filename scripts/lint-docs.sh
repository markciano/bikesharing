#!/usr/bin/env bash
# Lints docs/**/*.md as the CI job `docs` does. Run by the owner: bash scripts/lint-docs.sh
# Keep the version equal to the one markdownlint-cli2-action@v24 bundles (0.23.2); update both together.
set -euo pipefail

cd "$(dirname "$0")/.."
npx --yes markdownlint-cli2@0.23.2 "docs/**/*.md"
