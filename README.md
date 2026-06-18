# Forest Cover Type — Inference Endpoint

A small MLOps scaffold that takes the UCI Forest Cover Type classifier and ships
it as a deployed inference service.

- **Model**: `scikit-learn` RandomForest trained on a 50k subsample of UCI
  `covtype` (581k rows, 54 features → 7 classes).
- **Service**: FastAPI + Uvicorn, packaged in a Python 3.11 container.
- **Registry**: GitHub Container Registry (`ghcr.io`) — free for public repos.
- **Runtime**: Azure Container Apps on the consumption plan (scales to zero).
- **CI/CD**: GitHub Actions — lint + test on PR, build/push/deploy on merge.
  Azure auth via OIDC federated credential (no long-lived secret).

## Local quickstart

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,train]'

# Train once (downloads ~11 MB the first time, cached after that).
python -m train.train

# Run the API.
uvicorn app.main:app --reload

# In another shell:
curl localhost:8000/health
curl -X POST localhost:8000/predict \
  -H 'content-type: application/json' \
  -d @examples/spruce_fir.json
```

OpenAPI docs at `http://localhost:8000/docs`.

## Deploy to Azure (free tier)

See [`infra/README.md`](infra/README.md) for the one-time provisioning. Once it's
set up, the `deploy.yml` workflow runs on every merge to `main`.

## Layout

```
app/                  FastAPI service
  schemas.py          Pydantic request/response
  model.py            joblib loader + predict
  main.py             routes
train/
  train.py            Reproducible training script
models/               Output dir for model.joblib (gitignored)
tests/                pytest API tests
infra/                Azure setup walkthrough
.github/workflows/    ci.yml + deploy.yml
Dockerfile            Build artefact
```

## Cost shape

- GHCR storage: free for public repos.
- Azure Container Apps: free monthly grant covers ~180k vCPU-seconds and ~360k
  GiB-seconds. With scale-to-zero enabled and idle traffic, the app costs
  effectively €0/month. Set `min-replicas 0` when provisioning.
- The Azure free account gives $200 of credit for 30 days and 12 months of a few
  free services on top — comfortable headroom for a portfolio project.

## What this scaffold deliberately *doesn't* do

- No model registry (MLflow/Azure ML) — model is baked into the image. Fine for
  one model, not fine if you want rollbacks or A/B.
- No drift detection. Add `evidently` if you want it.
- No request authentication. Container Apps has an "auth" knob you can flip on
  if you don't want the endpoint open to the world.
- Trains in the same workflow as deploy. A real MLOps setup splits these so a
  bad training run can't take down prod.
