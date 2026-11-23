#!/usr/bin/env bash
# Every check of the monitoring configuration, as CI runs them: format, initialisation
# with the locked provider, validation and the tests against a mocked provider. Run it
# from the project root. None of them reaches Grafana Cloud or needs a credential.
set -euo pipefail

tf=(terraform -chdir=monitoring)

echo "== terraform fmt"
"${tf[@]}" fmt -check -recursive
echo "== terraform init"
"${tf[@]}" init -backend=false -lockfile=readonly
echo "== terraform validate"
"${tf[@]}" validate
echo "== terraform test"
"${tf[@]}" test
