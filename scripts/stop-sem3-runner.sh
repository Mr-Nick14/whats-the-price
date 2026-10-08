#!/usr/bin/env bash
set -euo pipefail

if ! docker container inspect gh-runner >/dev/null 2>&1; then
  echo "Runner container gh-runner is not present."
  exit 0
fi

kubeconfig_path=$(docker inspect gh-runner --format \
  '{{range .Mounts}}{{if eq .Destination "/home/runner/.kube/config"}}{{.Source}}{{end}}{{end}}')
docker rm -f gh-runner
if [[ "$kubeconfig_path" == /private/tmp/sem3-runner-kubeconfig.* ]]; then
  rm -f "$kubeconfig_path"
fi
echo "Runner container stopped. Remove the runner entry in GitHub Settings > Actions > Runners."
