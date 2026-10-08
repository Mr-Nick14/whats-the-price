#!/usr/bin/env bash
set -euo pipefail

: "${RUNNER_URL:?Set RUNNER_URL to the repository URL}"
: "${RUNNER_TOKEN:?Set RUNNER_TOKEN to a temporary GitHub runner registration token}"

./config.sh --unattended --url "$RUNNER_URL" --token "$RUNNER_TOKEN" \
  --name "${RUNNER_NAME:-ml-pro-sem3}" --labels kind --replace --work _work
unset RUNNER_TOKEN
exec ./run.sh
