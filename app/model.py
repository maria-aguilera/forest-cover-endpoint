from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np

from app.schemas import COVER_LABELS, PredictRequest, PredictResponse

MODEL_PATH = Path(os.getenv("MODEL_PATH", "models/model.joblib"))

NUMERIC_ORDER = (
    "elevation",
    "aspect",
    "slope",
    "horizontal_distance_to_hydrology",
    "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways",
    "hillshade_9am",
    "hillshade_noon",
    "hillshade_3pm",
    "horizontal_distance_to_fire_points",
)


@lru_cache(maxsize=1)
def load_model() -> dict:
    """Load the joblib bundle once per process. Raises if the file is missing —
    container should fail fast rather than serve nonsense."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found at {MODEL_PATH}. Run `python -m train.train` first."
        )
    return joblib.load(MODEL_PATH)


def _to_feature_vector(req: PredictRequest) -> np.ndarray:
    numeric = [getattr(req, name) for name in NUMERIC_ORDER]
    wilderness = [0.0] * 4
    wilderness[req.wilderness_area - 1] = 1.0
    soil = [0.0] * 40
    soil[req.soil_type - 1] = 1.0
    return np.array([numeric + wilderness + soil], dtype=np.float64)


def predict(req: PredictRequest) -> PredictResponse:
    bundle = load_model()
    estimator = bundle["estimator"]
    version = bundle.get("version", "unknown")

    x = _to_feature_vector(req)
    proba = estimator.predict_proba(x)[0]
    classes = estimator.classes_
    top_idx = int(np.argmax(proba))
    cover_type = int(classes[top_idx])

    probabilities = {
        COVER_LABELS[int(c)]: float(p) for c, p in zip(classes, proba, strict=True)
    }

    return PredictResponse(
        cover_type=cover_type,
        cover_label=COVER_LABELS[cover_type],
        probabilities=probabilities,
        model_version=version,
    )
