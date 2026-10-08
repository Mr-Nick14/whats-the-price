"""Проверка журнала запросов в настоящем PostgreSQL."""

import os
import uuid

import psycopg
import pytest


@pytest.fixture()
def database_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("для интеграционного теста нужен DATABASE_URL")
    return url


def logged_request(database_url, request_id):
    with psycopg.connect(database_url) as connection:
        return connection.execute(
            """SELECT model_version, features, prediction, latency_ms, status_code
               FROM predictions WHERE request_id = %s""",
            (request_id,),
        ).fetchone()


def test_successful_request_is_saved(client, good_row, database_url):
    response = client.post("/v1/predict", json=good_row)

    assert response.status_code == 200
    body = response.json()
    row = logged_request(database_url, body["request_id"])
    assert row is not None
    assert row[0] == body["model_version"]
    assert row[1] == good_row
    assert row[2] == pytest.approx(body["prediction"])
    assert row[3] >= 0
    assert row[4] == 200


def test_invalid_request_is_saved(client, good_row, database_url):
    invalid_row = {**good_row, "year": 1700, "model_name": str(uuid.uuid4())}
    response = client.post("/v1/predict", json=invalid_row)

    assert response.status_code == 422
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            """SELECT features, prediction, status_code FROM predictions
               WHERE features->>'model_name' = %s""",
            (invalid_row["model_name"],),
        ).fetchone()
    assert row == (invalid_row, None, 422)
