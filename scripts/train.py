"""Обучение модели цены и публикация версии в MLflow Registry."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from what_s_price.service.app import Features

FEATURES = list(Features.model_fields)
NUMERIC = ["year", "mileage", "engine_displacement", "horsepower"]
CATEGORICAL = [name for name in FEATURES if name not in NUMERIC]
TARGET = "price"


def file_md5(path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 - DVC uses MD5 as a content identifier.
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def make_pipeline(alpha: float) -> Pipeline:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler())])
    categorical = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")),
                            ("onehot", OneHotEncoder(handle_unknown="ignore"))])
    preprocess = ColumnTransformer([
        ("numeric", numeric, NUMERIC),
        ("categorical", categorical, CATEGORICAL),
    ])
    return Pipeline([("preprocess", preprocess), ("regressor", Ridge(alpha=alpha))])


def champion_mae(client: MlflowClient, model_name: str) -> float | None:
    try:
        version = client.get_model_version_by_alias(model_name, "champion")
    except MlflowException as exc:
        if exc.error_code == "RESOURCE_DOES_NOT_EXIST":
            return None
        raise
    metric = client.get_run(version.run_id).data.metrics.get("val_mae")
    if metric is None:
        raise ValueError(f"Champion version {version.version} has no val_mae metric")
    return float(metric)


def train(data_path: Path, model_name: str, alpha: float, min_gain: float) -> None:
    if not data_path.is_file():
        raise FileNotFoundError(data_path)
    data_md5 = file_md5(data_path)
    data = pd.read_csv(data_path, usecols=[TARGET, *FEATURES])
    data = data.drop_duplicates().loc[lambda frame: frame[TARGET].gt(0)]
    data = data.loc[data["year"].between(1886, 2021)].reset_index(drop=True)
    if len(data) < 100:
        raise ValueError("Training data must contain at least 100 valid rows")

    train_data, val_data = train_test_split(data, test_size=0.2, random_state=42)
    pipeline = make_pipeline(alpha)
    pipeline.fit(train_data[FEATURES], train_data[TARGET])
    predictions = pipeline.predict(val_data[FEATURES])
    mae = float(mean_absolute_error(val_data[TARGET], predictions))

    mlflow.set_experiment("what-s-price")
    client = MlflowClient()
    with mlflow.start_run() as run:
        mlflow.log_params({"alpha": alpha, "min_gain": min_gain, "data_md5": data_md5,
                           "data_path": str(data_path), "train_rows": len(train_data),
                           "validation_rows": len(val_data)})
        mlflow.log_metric("val_mae", mae)
        metadata = {"input_features": FEATURES, "target": TARGET, "data_md5": data_md5,
                    "decision_threshold": min_gain, "validation_mae": mae}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            mlflow.log_artifact(str(path))

        fig, ax = plt.subplots(figsize=(7, 4))
        residuals = val_data[TARGET].to_numpy() - predictions
        ax.hist(residuals, bins=60)
        ax.set(xlabel="Actual price minus prediction", ylabel="Cars",
               title="Validation residuals")
        fig.tight_layout()
        mlflow.log_figure(fig, "validation_residuals.png")
        plt.close(fig)

        previous_mae = champion_mae(client, model_name)
        info = mlflow.sklearn.log_model(
            pipeline,
            name="price-model",
            registered_model_name=model_name,
            metadata=metadata,
            serialization_format="cloudpickle",
        )
        version = info.registered_model_version
        if version is None:
            raise RuntimeError("MLflow did not return a registered model version")
        client.set_registered_model_alias(model_name, "challenger", version)
        promoted = previous_mae is None or previous_mae - mae >= min_gain
        if promoted:
            client.set_registered_model_alias(model_name, "champion", version)
        mlflow.set_tag("gate_decision", "promoted" if promoted else "rejected")
        print(json.dumps({"run_id": run.info.run_id, "version": version,
                          "data_md5": data_md5, "val_mae": mae,
                          "previous_mae": previous_mae,
                          "decision": "promoted" if promoted else "rejected"}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=Path("data/used_cars_sample.csv"))
    parser.add_argument("--model-name", default="what-s-price")
    parser.add_argument("--alpha", type=float, default=10.0)
    parser.add_argument("--min-gain", type=float, default=100.0,
                        help="Minimum validation MAE improvement in USD")
    args = parser.parse_args()
    if args.alpha < 0 or args.min_gain < 0:
        parser.error("alpha and min-gain must be non-negative")
    train(args.data_path, args.model_name, args.alpha, args.min_gain)


if __name__ == "__main__":
    main()
