"""Сохранять динамику HPA и CPU подов во время нагрузочного теста."""

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def kubectl(*args: str) -> str:
    result = subprocess.run(["kubectl", *args], check=True, capture_output=True, text=True)
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.duration

    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "timestamp_utc", "current_replicas", "desired_replicas", "cpu_utilization_pct",
            "pod_cpu_millicores", "pod_memory_mib",
        ])
        writer.writeheader()
        while True:
            hpa = json.loads(kubectl("get", "hpa", "what-s-price", "-o", "json"))
            status = hpa.get("status", {})
            metrics = status.get("currentMetrics", [])
            cpu = next((metric["resource"]["current"].get("averageUtilization")
                        for metric in metrics if metric.get("resource", {}).get("name") == "cpu"),
                       None)
            try:
                top = kubectl("top", "pods", "-l", "app=what-s-price", "--no-headers")
            except subprocess.CalledProcessError:
                top = ""
            pod_cpu = []
            pod_memory = []
            for line in top.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    pod_cpu.append(int(parts[1].rstrip("m")))
                    pod_memory.append(int(parts[2].rstrip("Mi")))
            writer.writerow({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "current_replicas": status.get("currentReplicas"),
                "desired_replicas": status.get("desiredReplicas"),
                "cpu_utilization_pct": cpu,
                "pod_cpu_millicores": ";".join(map(str, pod_cpu)),
                "pod_memory_mib": ";".join(map(str, pod_memory)),
            })
            stream.flush()
            if time.monotonic() >= deadline:
                break
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
