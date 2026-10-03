"""Central configuration, read from environment variables.

Decision: one module owns every setting so secrets/paths are never scattered or
hard-coded. Copy `.env.example` -> set the variables in your shell or hosting
platform. Nothing here has a secret default.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# TODO (Praise): set DATABASE_URL for deployment (e.g. a Postgres URL).
# Default is a local SQLite file, which needs no secret.
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")

# TODO (Praise): point UPLOAD_DIR at persistent storage when deploying.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "uploads"))

# TODO (Praise): set REGISTRATION_CODE to restrict who can create accounts.
# Empty/unset = open registration (development only).
REGISTRATION_CODE = os.environ.get("REGISTRATION_CODE", "")

# Model file contract (docs/MODEL_INTERFACE.md): .keras preferred, .h5 accepted.
MODEL_CANDIDATES = [BASE_DIR / "pneumonia_model.keras", BASE_DIR / "pneumonia_model.h5"]

# Upload limits (FR3 / FR13).
MAX_UPLOAD_MB = 10
ALLOWED_TYPES = ["jpg", "jpeg", "png"]

DEFAULT_THRESHOLD = 0.5
DEFAULT_OPACITY = 0.4
LIME_NUM_SAMPLES = 1000

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
