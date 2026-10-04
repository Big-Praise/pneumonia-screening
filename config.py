"""Central configuration, read from environment variables.

Decision: one module owns every setting so secrets/paths are never scattered or
hard-coded. Copy `.env.example` -> set the variables in your shell or hosting
platform. Nothing here has a secret default.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    # Neon/Heroku-style "postgres(ql)://" -> SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# TODO (Praise): set DATABASE_URL for deployment (e.g. the Neon Postgres URL).
# Default is a local SQLite file, which needs no secret.
DATABASE_URL = _db_url()

# TODO (Praise): point UPLOAD_DIR at persistent storage when deploying with BLOB_BACKEND=disk.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "uploads"))

# Where X-ray images and saved LIME results live: "disk" (UPLOAD_DIR) or "db"
# (a table in DATABASE_URL). Use "db" on hosts whose disk is wiped on restart
# (e.g. Hugging Face Spaces). The Streamlit app defaults to disk.
BLOB_BACKEND = os.environ.get("BLOB_BACKEND", "disk").lower()

# TODO (Praise): set REGISTRATION_CODE to restrict who can create accounts.
# Empty/unset = open registration (development only).
REGISTRATION_CODE = os.environ.get("REGISTRATION_CODE", "")

# --- API (FastAPI backend) only
# TODO (Praise): set JWT_SECRET (long random string) in the backend host's secrets.
# Unset = a random per-process secret: fine for local dev, but every restart
# logs everyone out, so production must set it.
JWT_SECRET = os.environ.get("JWT_SECRET", "")
SESSION_HOURS = 8
# Cookies are marked Secure (HTTPS-only) unless explicitly disabled for local http.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") != "0"

# Model file contract (docs/MODEL_INTERFACE.md): .keras preferred, .h5 accepted.
MODEL_CANDIDATES = [BASE_DIR / "pneumonia_model.keras", BASE_DIR / "pneumonia_model.h5"]
# TODO (Praise): in production set MODEL_HF_REPO (e.g. "Big-Praise/pneumonia-model") and
# HF_TOKEN (read-only token) so the backend downloads the private model at startup.
MODEL_HF_REPO = os.environ.get("MODEL_HF_REPO", "")
MODEL_HF_FILENAME = os.environ.get("MODEL_HF_FILENAME", "pneumonia_model.keras")

# Upload limits (FR3 / FR13).
MAX_UPLOAD_MB = 10
ALLOWED_TYPES = ["jpg", "jpeg", "png"]

DEFAULT_THRESHOLD = 0.5
DEFAULT_OPACITY = 0.4
LIME_NUM_SAMPLES = int(os.environ.get("LIME_NUM_SAMPLES", "1000"))

if BLOB_BACKEND == "disk":
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
