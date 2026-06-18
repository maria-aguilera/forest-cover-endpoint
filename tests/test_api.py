from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier

from app import model as model_module


@pytest.fixture(scope="session", autouse=True)
def _ensure_tiny_model(tmp_path_factory) -> None:
    """Train a 200-row stub model so the API has something to load in CI without
    pulling the full UCI dataset. Production deploys use the real `train/train.py`."""
    rng = np.random.default_rng(0)
    n = 200
    n_features = 54
    X = rng.random((n, n_features)) * 100
    X[:, 10:14] = 0
    X[:, 14:] = 0
    rng.integers(0, 4, size=n)
    for i in range(n):
        X[i, 10 + rng.integers(0, 4)] = 1
        X[i, 14 + rng.integers(0, 40)] = 1
    y = rng.integers(1, 8, size=n)

    clf = RandomForestClassifier(n_estimators=20, random_state=0)
    clf.fit(X, y)

    out = Path(tmp_path_factory.mktemp("models") / "model.joblib")
    joblib.dump(
        {
            "estimator": clf,
            "version": datetime.now(UTC).strftime("test-%Y%m%d%H%M%S"),
            "metrics": {"accuracy": 0.0, "n_train": n},
        },
        out,
    )

    model_module.MODEL_PATH = out
    model_module.load_model.cache_clear()


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def _example_request() -> dict:
    return {
        "elevation": 2596,
        "aspect": 51,
        "slope": 3,
        "horizontal_distance_to_hydrology": 258,
        "vertical_distance_to_hydrology": 0,
        "horizontal_distance_to_roadways": 510,
        "hillshade_9am": 221,
        "hillshade_noon": 232,
        "hillshade_3pm": 148,
        "horizontal_distance_to_fire_points": 6279,
        "wilderness_area": 1,
        "soil_type": 29,
    }


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_predict_shape(client: TestClient) -> None:
    r = client.post("/predict", json=_example_request())
    assert r.status_code == 200, r.text
    body = r.json()
    assert 1 <= body["cover_type"] <= 7
    assert isinstance(body["cover_label"], str)
    assert 0.999 < sum(body["probabilities"].values()) < 1.001
    assert body["model_version"].startswith("test-")


def test_predict_rejects_bad_soil(client: TestClient) -> None:
    bad = _example_request() | {"soil_type": 99}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422


def test_predict_rejects_bad_wilderness(client: TestClient) -> None:
    bad = _example_request() | {"wilderness_area": 7}
    r = client.post("/predict", json=bad)
    assert r.status_code == 422
