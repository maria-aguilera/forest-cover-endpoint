"""Train a baseline RandomForest on the UCI Forest Cover Type dataset.

Subsamples the 581k rows down to 50k so the training fits in CI within a couple
of minutes. The point of this script is reproducibility of the deployment
artefact, not chasing accuracy — for that, swap in the tuned pipeline from the
sister notebook repo.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.datasets import fetch_covtype
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("train")

DEFAULT_OUTPUT = Path("models/model.joblib")
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--sample-size", type=int, default=50_000)
    p.add_argument("--n-estimators", type=int, default=200)
    p.add_argument("--max-depth", type=int, default=None)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Fetching UCI covtype (cached after first run)...")
    data = fetch_covtype(as_frame=False)
    X, y = data.data, data.target

    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(X), size=min(args.sample_size, len(X)), replace=False)
    X, y = X[idx], y[idx]
    logger.info("Training on %d rows, %d features.", X.shape[0], X.shape[1])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    started = time.perf_counter()
    clf = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        n_jobs=-1,
        random_state=RANDOM_STATE,
    )
    clf.fit(X_train, y_train)
    elapsed = time.perf_counter() - started

    preds = clf.predict(X_test)
    acc = accuracy_score(y_test, preds)
    logger.info("Trained in %.1fs. Test accuracy: %.4f", elapsed, acc)
    logger.info("Per-class report:\n%s", classification_report(y_test, preds, digits=3))

    bundle = {
        "estimator": clf,
        "version": datetime.now(UTC).strftime("%Y%m%d-%H%M%S"),
        "metrics": {"accuracy": float(acc), "n_train": int(X_train.shape[0])},
        "config": vars(args) | {"random_state": RANDOM_STATE},
    }
    joblib.dump(bundle, args.output, compress=3)
    logger.info("Saved bundle to %s (version=%s)", args.output, bundle["version"])


if __name__ == "__main__":
    main()
