#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
runner_url=https://github.com/Mr-Nick14/whats-the-price
if [[ -z ${RUNNER_TOKEN:-} ]] && command -v gh >/dev/null \
  && gh auth status >/dev/null 2>&1; then
  RUNNER_TOKEN=$(gh api --method POST \
    repos/Mr-Nick14/whats-the-price/actions/runners/registration-token \
    --jq .token)
fi
if [[ -z ${RUNNER_TOKEN:-} ]]; then
  read -r -s -p "GitHub runner registration token: " RUNNER_TOKEN
  echo
fi
: "${RUNNER_TOKEN:?Get a temporary token from GitHub Settings > Actions > Runners}"

cluster_name=ml-pro-sem3
kubeconfig_path="$(mktemp /private/tmp/sem3-runner-kubeconfig.XXXXXX)"
trap 'rm -f "$kubeconfig_path"' EXIT
kind get kubeconfig --name "$cluster_name" > "$kubeconfig_path"
kubectl --kubeconfig "$kubeconfig_path" config set-cluster "kind-$cluster_name" \
  --server="https://$cluster_name-control-plane:6443" >/dev/null
chmod 600 "$kubeconfig_path"

docker build -f platform/runner/Dockerfile -t ml-pro-sem3-runner:local .
docker run -d --name gh-runner --network kind --group-add 0 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$kubeconfig_path:/home/runner/.kube/config:ro" \
  -e "RUNNER_URL=$runner_url" -e "RUNNER_TOKEN=$RUNNER_TOKEN" \
  -e RUNNER_NAME=ml-pro-sem3 ml-pro-sem3-runner:local

trap - EXIT
echo "Runner container started. Check docker logs gh-runner and GitHub Settings > Actions > Runners."
echo "Stop it with bash scripts/stop-sem3-runner.sh."
