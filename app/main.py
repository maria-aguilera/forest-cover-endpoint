from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.model import load_model, predict
from app.schemas import PredictRequest, PredictResponse

logger = logging.getLogger("forest_cover_endpoint")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


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
