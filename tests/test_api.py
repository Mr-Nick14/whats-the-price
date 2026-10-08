"""Проверки состояния и ошибок ввода."""

from fastapi.testclient import TestClient

from what_s_price import db
from what_s_price.config import settings
from what_s_price.service.app import app


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model_version": "0.1.0",
        "model_path": "artifacts/missing.joblib",
    }


def test_ready(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_bad_year_is_422(client, good_row) -> None:
    response = client.post("/v1/predict", json={**good_row, "year": 1700})
    assert response.status_code == 422


def test_extra_field_is_422(client, good_row) -> None:
    response = client.post("/v1/predict", json={**good_row, "unexpected": "value"})
    assert response.status_code == 422


def test_missing_field_is_422(client, good_row) -> None:
    request_without_model = dict(good_row)
    del request_without_model["model_name"]
    response = client.post("/v1/predict", json=request_without_model)
    assert response.status_code == 422


def test_invalid_request_is_logged_with_422(client, good_row, monkeypatch) -> None:
    logged_rows: list[tuple[object, ...]] = []
    monkeypatch.setattr(db, "save_prediction", lambda *args: logged_rows.append(args))

    response = client.post("/v1/predict", json={**good_row, "year": 1700})

    assert response.status_code == 422
    assert len(logged_rows) == 1
    assert logged_rows[0][2] is None
    assert logged_rows[0][-1] == 422


def test_model_failure_is_logged_with_500(good_row, monkeypatch) -> None:
    logged_rows: list[tuple[object, ...]] = []
    monkeypatch.setattr(db, "save_prediction", lambda *args: logged_rows.append(args))

    with TestClient(app, raise_server_exceptions=False) as client:
        def fail_prediction(_frame):
            raise RuntimeError("model unavailable")

        monkeypatch.setattr(app.state.pipeline, "predict", fail_prediction)
        response = client.post("/v1/predict", json=good_row)

    assert response.status_code == 500
    assert response.json() == {"detail": "Prediction failed"}
    assert len(logged_rows) == 1
    assert logged_rows[0][2] is None
    assert logged_rows[0][-1] == 500
