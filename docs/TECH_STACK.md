# Tech Stack — Full-Stack v2

Chosen so a fast shipper can build quickly but still have a real backend + DB.
Two acceptable paths are given; the agent should pick ONE and confirm with the
user before building. Default = Path A unless the user says otherwise.

## Path A (default) — Streamlit + SQLite + SQLAlchemy
Fastest route that still has real auth, a real database, and image storage.
- **Streamlit** — UI (keeps the team's existing experience and the current app).
- **SQLite** — a single-file database (`app.db`). Zero setup, perfect for a
  demo and a single-machine clinical tool; can be swapped for Postgres later.
- **SQLAlchemy** — ORM so the data layer is clean and portable (SQLite now,
  Postgres later with minimal change).
- **streamlit-authenticator** (or a simple bcrypt-based login) — clinician auth.
- **bcrypt / passlib** — password hashing.
- Image storage: save uploaded files under `uploads/` and store the path in the
  DB (simpler than blobs; fine for a demo). Blobs in SQLite are an option if the
  user prefers everything in one file.

## Path B — FastAPI backend + React frontend + Postgres
A "real" production-style split. More impressive, more work. Only choose this if
the user explicitly wants a separate frontend/backend and has the time.
- **FastAPI** backend (REST), **React** frontend, **PostgreSQL** + SQLAlchemy,
  JWT auth. The model served behind a `/predict` endpoint.
- Note to agent: this is heavier. Confirm the timeline before committing to it.

## Shared / model + explainability (both paths)
- **Python 3.10+**, **TensorFlow/Keras** (load `pneumonia_model.keras`), **NumPy**,
  **Pillow**, **OpenCV** (Grad-CAM overlay).
- **lime** (the `lime` Python library, `lime_image`) for LIME explanations.
- **scikit-image** — LIME uses it for superpixel segmentation.
- **reportlab** or **fpdf2** — generate the exportable PDF report.
- **matplotlib** — colour-mapping heatmaps if not using OpenCV.

## Do NOT (without asking)
- Do not hard-code secrets or a default admin password.
- Do not store real patient-identifying data during development.
- Do not send images to any external API for inference.

## requirements.txt (Path A baseline)
```
streamlit
tensorflow
numpy
pillow
opencv-python-headless
lime
scikit-image
sqlalchemy
passlib[bcrypt]
reportlab
matplotlib
```

## Target layout (Path A)
```
app.py                  # Streamlit entry: routing between login / scan / history
auth.py                 # register, login, password hashing, session
db.py                   # SQLAlchemy models + session (User, Patient, Scan)
model_loader.py         # cached model load (+ mock fallback)
predict.py              # preprocess -> infer -> (label, confidence)
gradcam.py              # Grad-CAM heatmap + overlay
lime_explain.py         # LIME explanation (lime_image) -> mask image
report.py               # build a PDF report for a scan
mock_predictor.py       # stand-in until pneumonia_model.keras is present
uploads/                # saved X-ray images
app.db                  # SQLite database (created at runtime)
requirements.txt
```
