"""Создать небольшую воспроизводимую выборку из исходного CSV домашки 1."""

import argparse
from pathlib import Path

import pandas as pd

from what_s_price.service.app import Features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("used_cars_data.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/used_cars_sample.csv"))
    parser.add_argument("--modulo", type=int, default=12)
    args = parser.parse_args()
    if args.modulo < 1:
        parser.error("modulo must be positive")
    if not args.source.is_file():
        parser.error(f"source CSV not found: {args.source}")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    columns = ["listing_id", "price", *Features.model_fields]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source_rows = sample_rows = 0
    with args.output.open("w", encoding="utf-8", newline="") as output:
        for chunk in pd.read_csv(args.source, usecols=columns, chunksize=100_000):
            source_rows += len(chunk)
            ids = pd.to_numeric(chunk["listing_id"], errors="coerce")
            selected = chunk.loc[ids.notna() & ids.mod(args.modulo).eq(0), columns]
            sample_rows += len(selected)
            selected.to_csv(output, index=False, header=source_rows == len(chunk))
    print(f"Source rows: {source_rows}; sample rows: {sample_rows}; output: {args.output}")


if __name__ == "__main__":
    main()
