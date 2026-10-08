#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
: "${RUNNER_TOKEN:?Paste a temporary token from GitHub Settings > Actions > Runners}"

cluster_name=ml-pro-sem3
runner_url=https://github.com/Mr-Nick14/whats-the-price
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
echo "Remove $kubeconfig_path after stopping the runner."
