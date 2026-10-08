#!/usr/bin/env bash
set -euo pipefail

kubectl port-forward service/what-s-price 8080:80 >/tmp/what-s-price-forward.log 2>&1 &
forward_pid=$!
trap 'kill "$forward_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if curl --fail --silent http://localhost:8080/ready >/dev/null; then
    break
  fi
  sleep 1
done

curl --fail --silent http://localhost:8080/health \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["model_path"] == "artifacts/model.joblib", r'

request_id=$(curl --fail --silent --show-error -X POST http://localhost:8080/v1/predict \
  -H 'Content-Type: application/json' --data-binary @good.json \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert 0 < r["prediction"] < 10000000, r; print(r["request_id"])')

kubectl exec deploy/postgres -- psql -U postgres -d what_s_price -tAc \
  "SELECT count(*) FROM predictions WHERE request_id = '$request_id' AND status_code = 200" \
  | grep -qx 1
