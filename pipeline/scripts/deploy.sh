#!/usr/bin/env bash
# Deploys the pipeline's Modal app and checks the deployment with one run. It is the
# only way to deploy the app (d007 D6, Deployments tagged with their commit); it takes
# no arguments, so the owner's machine and CI run it the same way (d008, Deploy
# script). Runs from any folder.
#
#   1. Refuses unless the working tree is clean, untracked files included, and HEAD is
#      origin/main. The commit is on main, so its PR's checks already passed.
#   2. Deploys with the full commit SHA as Modal's tag and as the image's CODE_VERSION,
#      so that every row and event of the deployment carries it.
#   3. Invokes the deployed scheduled function once and waits for it (smoke test).
#
# A faulty deployment is never undone by deploying an older commit: a PR that reverts
# it is merged and deployed like any other.
set -euo pipefail

cd "$(dirname "$0")/.."

# Prints what stopped the deployment and leaves; nothing has been deployed yet.
refuse() {
  echo "error: refusing to deploy: $1" >&2
  if [[ -n ${2:-} ]]; then
    echo "$2" >&2
  fi
  exit 1
}

git fetch --quiet origin main

status=$(git status --porcelain --untracked-files=all)
uncommitted=$(grep -v '^??' <<<"$status" || true)
untracked=$(grep '^??' <<<"$status" || true)
if [[ -n $uncommitted ]]; then
  refuse "the working tree has uncommitted changes:" "$uncommitted"
fi
if [[ -n $untracked ]]; then
  refuse "the working tree has untracked files:" "$untracked"
fi

sha=$(git rev-parse HEAD)
main_sha=$(git rev-parse origin/main)
if [[ $sha != "$main_sha" ]]; then
  refuse "HEAD ($sha) is not origin/main ($main_sha)."
fi

echo "== modal deploy ($sha)"
# `--locked` fails when `uv.lock` does not match `pyproject.toml`; the variable
# reaches only the build of the image, which stores it.
CODE_VERSION="$sha" uv run --locked --group platform modal deploy --tag "$sha" modal_app.py

echo "== smoke test"
uv run --locked --group platform python scripts/smoke_test.py
