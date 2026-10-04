# Backend container for Hugging Face Spaces (Docker SDK). Builds on HF's servers.
# Serves only the FastAPI app (api/) + the shared ML/data modules — no Streamlit.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    # Space disk is wiped on restart: keep images + LIME results in Postgres.
    BLOB_BACKEND=db

# HF Spaces run containers as uid 1000.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

COPY --chown=user requirements-api.txt .
RUN pip install --no-cache-dir --user -r requirements-api.txt

COPY --chown=user *.py ./
COPY --chown=user api ./api

EXPOSE 7860
# --proxy-headers: HF terminates HTTPS in front of the container.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
