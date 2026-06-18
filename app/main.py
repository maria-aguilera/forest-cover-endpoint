from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pythonjsonlogger import jsonlogger

from app.model import load_model, predict
from app.schemas import PredictRequest, PredictResponse

# Structured JSON logging — every line is a single JSON object queryable in
# Log Analytics by field instead of by regex.
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(
    jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
)
_root = logging.getLogger()
_root.handlers = [_handler]
_root.setLevel(logging.INFO)
logger = logging.getLogger("forest_cover_endpoint")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        bundle = load_model()
        logger.info("Loaded model version=%s", bundle.get("version", "unknown"))
    except FileNotFoundError as exc:
        logger.error("Startup failed: %s", exc)
        raise
    yield


app = FastAPI(
    title="Forest Cover Type Endpoint",
    description="Inference service for the UCI Forest Cover Type classifier.",
    version="0.1.0",
    lifespan=lifespan,
)

# Prometheus metrics exposed at /metrics — request count, latency histogram,
# in-flight requests, and per-handler labels.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "forest-cover-endpoint",
        "docs": "/docs",
        "health": "/health",
        "predict": "POST /predict",
    }


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(req: PredictRequest) -> PredictResponse:
    try:
        return predict(req)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
