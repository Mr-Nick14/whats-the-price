#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ingress_url="${INGRESS_URL:-http://${KIND_CLUSTER:-ml-pro-sem3}-control-plane}"
host_header='Host: price.localhost'

for _ in $(seq 1 30); do
  if curl --silent --fail --connect-timeout 3 --max-time 10 \
    -H "$host_header" "$ingress_url/ready" >/dev/null; then
    break
  fi
  sleep 2
done

curl --fail --silent --show-error --connect-timeout 3 --max-time 10 \
  -H "$host_header" "$ingress_url/health" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["model_path"].startswith("models:/what-s-price/"), r; assert r["model_version"].isdigit(), r'

request_id=$(curl --fail --silent --show-error --connect-timeout 3 --max-time 10 \
  -H "$host_header" \
  -H 'Content-Type: application/json' -X POST "$ingress_url/v1/predict" \
  --data-binary @good.json \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert 0 < r["prediction"] < 10000000, r; print(r["request_id"])')

kubectl exec deploy/postgres -- psql -U postgres -d what_s_price -tAc \
  "SELECT count(*) FROM predictions WHERE request_id = '$request_id' AND status_code = 200" \
  | grep -qx 1

echo "Smoke passed: registry model, prediction and database row $request_id"
