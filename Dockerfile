# Backend container (FastAPI + TensorFlow). Built by Google Cloud Build from the
# GitHub repo and run on Cloud Run. Serves only api/ + the shared ML/data modules.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    # Container disk is temporary: keep images + LIME results in Postgres.
    BLOB_BACKEND=db \
    # Cloud Run gives CPU only during startup and requests: load the model at startup.
    MODEL_LOAD_BLOCKING=1

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

COPY --chown=user requirements-api.txt .
RUN pip install --no-cache-dir --user -r requirements-api.txt

COPY --chown=user auth.py blobstore.py config.py db.py gradcam.py lime_explain.py \
     mock_predictor.py model_loader.py predict.py report.py storage.py ./
COPY --chown=user api ./api

# Cloud Run sets $PORT (8080). --proxy-headers: HTTPS ends at Google's front end.
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips "*"
