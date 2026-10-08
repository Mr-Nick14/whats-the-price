"""API для оценки цены автомобиля."""

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from what_s_price import db
from what_s_price.config import settings


class Features(BaseModel):
    """Признаки модели."""

    model_config = ConfigDict(extra="forbid", strict=True)

    make_name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1886, le=2021)
    mileage: float | None = Field(default=None, ge=0, le=1_000_000)
    engine_displacement: float | None = Field(default=None, ge=0, le=10_000)
    horsepower: float | None = Field(default=None, ge=0, le=2_000)
    fuel_type: str | None = Field(default=None, min_length=1, max_length=100)
    transmission_display: str | None = Field(default=None, min_length=1, max_length=100)
    body_type: str | None = Field(default=None, min_length=1, max_length=100)
    wheel_system: str | None = Field(default=None, min_length=1, max_length=100)
    is_new: bool
    has_accidents: bool | None = None


class Prediction(BaseModel):
    prediction: float
    model_version: str
    request_id: str
    latency_ms: float


class BatchRequest(BaseModel):
    rows: list[Features] = Field(min_length=1, max_length=1000)


class BatchPrediction(BaseModel):
    predictions: list[float]
    model_version: str
    request_id: str
    latency_ms: float


def load_model_bundle(path: Path) -> tuple[Any, dict[str, Any]]:
    """Проверить артефакт и порядок признаков."""
    if not path.is_file():
        raise FileNotFoundError(f"Model artifact not found: {path}")

    bundle = joblib.load(path)
    if not isinstance(bundle, dict) or not {"pipeline", "metadata"} <= bundle.keys():
        raise ValueError("Model artifact must contain pipeline and metadata")

    pipeline, metadata = bundle["pipeline"], bundle["metadata"]
    if not hasattr(pipeline, "predict") or not isinstance(metadata, dict):
        raise ValueError("Model artifact has an invalid pipeline or metadata")
    if not {"input_features", "model_version"} <= metadata.keys():
        raise ValueError("Model metadata is missing input_features or model_version")
    if list(metadata["input_features"]) != list(Features.model_fields):
        raise ValueError("API schema does not match the model artifact feature order")

    return pipeline, metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline, metadata = load_model_bundle(Path(settings.model_path))
    app.state.pipeline = pipeline
    app.state.meta = metadata
    app.state.version = metadata["model_version"]
    db.init()
    try:
        yield
    finally:
        app.state.pipeline = None
        app.state.meta = None


app = FastAPI(title="what-s-price", version="1.0", lifespan=lifespan)


@app.middleware("http")
async def remember_prediction_start(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/v1/predict":
        request.state.started_at = time.perf_counter()
        request.state.request_id = str(uuid.uuid4())
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def log_invalid_prediction(request: Request, exc: RequestValidationError):
    response = await request_validation_exception_handler(request, exc)
    if request.method == "POST" and request.url.path == "/v1/predict":
        payload = exc.body if isinstance(exc.body, dict) else {"_invalid_body": str(exc.body)}
        latency_ms = round((time.perf_counter() - request.state.started_at) * 1000, 2)
        response.background = BackgroundTask(
            db.save_prediction,
            request.state.request_id,
            payload,
            None,
            getattr(request.app.state, "version", "unknown"),
            latency_ms,
            422,
        )
    return response


@app.exception_handler(Exception)
async def log_failed_prediction(request: Request, exc: Exception):
    if request.method != "POST" or request.url.path != "/v1/predict":
        raise exc

    payload = getattr(request.state, "features", {"_invalid_body": "unavailable"})

    latency_ms = round((time.perf_counter() - request.state.started_at) * 1000, 2)
    return JSONResponse(
        status_code=500,
        content={"detail": "Prediction failed"},
        background=BackgroundTask(
            db.save_prediction,
            request.state.request_id,
            payload,
            None,
            getattr(request.app.state, "version", "unknown"),
            latency_ms,
            500,
        ),
    )


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "model_version": getattr(request.app.state, "version", "unknown"),
        "model_path": settings.model_path,
    }


@app.get("/ready")
def ready(request: Request) -> dict[str, str]:
    if getattr(request.app.state, "pipeline", None) is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


@app.post("/v1/predict")
def predict(x: Features, bg: BackgroundTasks, request: Request) -> Prediction:
    request_id = request.state.request_id
    payload = x.model_dump()
    request.state.features = payload
    frame = pd.DataFrame([payload]).reindex(columns=request.app.state.meta["input_features"])

    price = float(request.app.state.pipeline.predict(frame)[0])
    latency_ms = round((time.perf_counter() - request.state.started_at) * 1000, 2)

    bg.add_task(
        db.save_prediction,
        request_id,
        payload,
        price,
        request.app.state.version,
        latency_ms,
        200,
    )

    return Prediction(
        prediction=price,
        model_version=request.app.state.version,
        request_id=request_id,
        latency_ms=latency_ms,
    )


@app.post("/v1/predict/batch")
def predict_batch(batch: BatchRequest, request: Request) -> BatchPrediction:
    started_at = time.perf_counter()
    payload = [row.model_dump() for row in batch.rows]
    frame = pd.DataFrame(payload).reindex(columns=request.app.state.meta["input_features"])
    prices = [float(value) for value in request.app.state.pipeline.predict(frame)]

    return BatchPrediction(
        predictions=prices,
        model_version=request.app.state.version,
        request_id=str(uuid.uuid4()),
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )
