#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
for command in kind kubectl helm; do
  command -v "$command" >/dev/null || { echo "$command is required" >&2; exit 1; }
done

cluster_name=ml-pro-sem3
if ! kind get clusters | grep -Fxq "$cluster_name"; then
  kind create cluster --name "$cluster_name" --config platform/kind-config.yaml
fi
kubectl config use-context "kind-$cluster_name"
kubectl label node "$cluster_name-control-plane" ingress-ready=true --overwrite

helm repo add traefik https://traefik.github.io/charts
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update
helm upgrade --install traefik traefik/traefik -n traefik --create-namespace \
  --version 41.7.0 -f platform/traefik-values.yaml --wait
helm upgrade --install metrics-server metrics-server/metrics-server -n kube-system \
  --version 3.14.0 -f platform/metrics-server-values.yaml --wait

kubectl apply -f platform/mlflow.yaml
kubectl rollout status deploy/mlflow -n mlops --timeout=300s
kubectl get pods,ingress -A
