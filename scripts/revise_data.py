"""Версия 2: убрать дубли и строки без пробега из DVC-выборки."""

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=Path("data/used_cars_sample.csv"))
    args = parser.parse_args()
    path = args.data_path
    data = pd.read_csv(path)
    cleaned = data.drop_duplicates().dropna(subset=["mileage"])
    temporary = path.with_suffix(".next.csv")
    cleaned.to_csv(temporary, index=False)
    temporary.replace(path)
    print(f"Version 2: {len(data)} -> {len(cleaned)} rows; removed {len(data) - len(cleaned)}")


if __name__ == "__main__":
    main()
