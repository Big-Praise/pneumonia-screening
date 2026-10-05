"""FastAPI backend for the Next.js frontend. Run from the repo root:

    uvicorn api.main:app --port 8000

Reuses the same modules as the Streamlit app (auth, db, predict, gradcam,
lime_explain, report, storage); this file is only HTTP plumbing. Every
data endpoint requires a logged-in clinician and is scoped to their own records.
Handlers are plain `def` so FastAPI runs the CPU-heavy ones in a thread pool
instead of blocking the event loop.
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import auth
import config
import db
import predict
import storage
from api import security
from api.services import THUMB_PX, DISPLAY_PX, lime_jobs, model
from api import services

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

DISCLAIMER = (
    "Decision-support only — not a diagnosis. This tool gives a screening result from a "
    "machine-learning model. It can miss cases and over-flag normal X-rays. A qualified "
    "clinician must make the final decision."
)
LIMITATIONS = [
    "The model can miss pneumonia and can over-flag normal X-rays.",
    "Training data was likely pediatric and single-source; performance on other populations "
    "or scanners is unknown.",
    "Sliders change how a result is displayed, not the model itself.",
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    if config.MODEL_LOAD_BLOCKING:
        await run_in_threadpool(model.load_now)   # Cloud Run: finish while startup has CPU
    else:
        model.start_loading()
    if security.USING_EPHEMERAL_SECRET:
        log.warning("JWT_SECRET not set: using a temporary secret (sessions end on restart).")
    yield


app = FastAPI(
    title="Pneumonia Screening API", lifespan=lifespan,
    docs_url="/api/docs" if os.environ.get("API_DOCS") == "1" else None,
    redoc_url=None, openapi_url="/api/openapi.json" if os.environ.get("API_DOCS") == "1" else None,
)

User = security.current_user  # dependency alias for readability


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception):
    # Stack trace to the server log only; the client gets a generic message.
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse({"detail": "Something went wrong. No result was changed."}, status_code=500)


# ------------------------------------------------------------------ helpers

def iso(dt: datetime | None) -> str | None:
    return db.as_utc(dt).isoformat().replace("+00:00", "Z") if dt else None


def patient_json(p: db.Patient) -> dict:
    return {"id": p.id, "name": p.name, "age": p.age, "sex": p.sex, "note": p.note,
            "created_at": iso(p.created_at)}


def scan_json(s: db.Scan) -> dict:
    return {"id": s.id, "patient_id": s.patient_id, "created_at": iso(s.created_at),
            "predicted_label": s.predicted_label, "confidence": s.confidence,
            "pneumonia_prob": s.pneumonia_prob, "threshold_used": s.threshold_used}


def owned_scan(user: auth.AuthUser, scan_id: int) -> tuple[db.Scan, db.Patient]:
    try:
        return db.get_scan(user.id, scan_id)
    except db.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found.") from None


def require_model():
    st = model.status()
    if st["status"] == "loading":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The screening model is still loading. Try again in a moment.")
    if st["status"] == "error":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The screening model could not be loaded, so no result can be produced.")
    return model.predictor


def image_response(data: bytes, media: str = "image/jpeg") -> Response:
    # Stored images never change, so the browser may cache them (privately).
    return Response(data, media_type=media, headers={"Cache-Control": "private, max-age=3600"})


# ------------------------------------------------------------------ public

@app.get("/")
def root():
    # The Space's landing URL: point humans at the real UI, reveal nothing else.
    return {"service": "Pneumonia Screening API", "note": "Decision-support only — not a diagnosis.",
            "health": "/api/health"}


@app.get("/api/health")
def health():
    return {"ok": True, "model": model.status()["status"]}


@app.get("/api/meta")
def meta():
    return {
        "disclaimer": DISCLAIMER, "limitations": LIMITATIONS,
        "registration_requires_code": auth.registration_requires_code(),
        "model": model.status(),
        "default_threshold": config.DEFAULT_THRESHOLD, "default_opacity": config.DEFAULT_OPACITY,
        "lime_num_samples": config.LIME_NUM_SAMPLES,
        "max_upload_mb": config.MAX_UPLOAD_MB,
    }


# ------------------------------------------------------------------ auth

class RegisterIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=200)
    full_name: str = Field(default="", max_length=128)
    registration_code: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=200)


def user_json(u: auth.AuthUser) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name,
            "display_name": u.display_name}


@app.post("/api/auth/register")
def register(body: RegisterIn, response: Response):
    try:
        user = auth.register_user(body.username, body.password, body.full_name,
                                  body.registration_code)
    except auth.AuthError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    security.issue(response, user)
    return user_json(user)


@app.post("/api/auth/login")
def login(body: LoginIn, response: Response):
    name = auth.normalise_username(body.username)
    security.throttle.check(name)
    user = auth.authenticate(body.username, body.password)
    if user is None:
        security.throttle.failed(name)
        # Same message for unknown user and wrong password.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")
    security.throttle.succeeded(name)
    security.issue(response, user)
    return user_json(user)


@app.post("/api/auth/logout")
def logout(response: Response):
    security.clear(response)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: auth.AuthUser = Depends(User)):
    return user_json(user)


# ------------------------------------------------------------------ dashboard + patients

@app.get("/api/dashboard")
def dashboard(user: auth.AuthUser = Depends(User)):
    n_patients, n_scans = db.count_for_user(user.id)
    recent = [{**scan_json(s), "patient_name": p.name} for s, p in db.recent_scans(user.id, 10)]
    return {"patients": n_patients, "scans": n_scans, "recent": recent}


class PatientIn(BaseModel):
    name: str = Field(max_length=128)
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=2000)


@app.get("/api/patients")
def list_patients(user: auth.AuthUser = Depends(User)):
    return [{**patient_json(p), "scan_count": n, "last_scan_at": iso(last)}
            for p, n, last in db.patient_summaries(user.id)]


@app.post("/api/patients", status_code=201)
def create_patient(body: PatientIn, user: auth.AuthUser = Depends(User)):
    try:
        p = db.create_patient(user.id, body.name, body.age, body.sex, body.note)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    return patient_json(p)


@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: int, user: auth.AuthUser = Depends(User)):
    try:
        p = db.get_patient(user.id, patient_id)
        scans = db.scans_for_patient(user.id, patient_id)
    except db.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.") from None
    return {**patient_json(p), "scans": [scan_json(s) for s in scans]}


# ------------------------------------------------------------------ scans

@app.post("/api/patients/{patient_id}/scans", status_code=201)
def create_scan(patient_id: int, file: UploadFile = File(...),
                user: auth.AuthUser = Depends(User)):
    try:
        db.get_patient(user.id, patient_id)
    except db.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found.") from None
    predictor = require_model()
    # Read at most limit+1 bytes so an oversized upload is rejected without buffering it all.
    data = file.file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    try:
        img = storage.load_upload(data)
    except storage.ImageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    try:
        p = predict.pneumonia_probability(predictor, img)
    except Exception:  # noqa: BLE001 — never fabricate a result
        log.exception("Prediction failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "The model could not process this image. No result was produced.") from None
    label, conf = predict.classify(p, config.DEFAULT_THRESHOLD)
    rel = storage.save_image(img)
    try:
        scan = db.create_scan(user.id, patient_id, rel, label, conf, p, config.DEFAULT_THRESHOLD)
    except Exception:
        storage.delete_image(rel)  # no orphan images
        raise
    return scan_json(scan)


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: int, user: auth.AuthUser = Depends(User)):
    scan, patient = owned_scan(user, scan_id)
    return {**scan_json(scan), "patient": patient_json(patient),
            "lime": lime_jobs.status(scan.image_path),
            "model": model.status()}


class ThresholdIn(BaseModel):
    threshold: float = Field(ge=0.0, le=1.0)


@app.patch("/api/scans/{scan_id}")
def save_threshold(scan_id: int, body: ThresholdIn, user: auth.AuthUser = Depends(User)):
    try:
        scan = db.update_scan_threshold(user.id, scan_id, body.threshold)
    except db.NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scan not found.") from None
    return scan_json(scan)


@app.get("/api/scans/{scan_id}/image")
def scan_image(scan_id: int, thumb: bool = False, user: auth.AuthUser = Depends(User)):
    scan, _ = owned_scan(user, scan_id)
    try:
        return image_response(services.image_jpeg(scan.image_path, THUMB_PX if thumb else DISPLAY_PX))
    except storage.ImageError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from None


def _label(label: str) -> str:
    if label not in (predict.NORMAL, predict.PNEUMONIA):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "label must be NORMAL or PNEUMONIA")
    return label


@app.get("/api/scans/{scan_id}/gradcam")
def scan_gradcam(scan_id: int, label: str, user: auth.AuthUser = Depends(User)):
    scan, _ = owned_scan(user, scan_id)
    require_model()
    try:
        return image_response(services.gradcam_jpeg(scan.image_path, _label(label)))
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — honest error, never a fake map
        log.exception("Grad-CAM failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "Grad-CAM could not be computed for this image.") from None


@app.get("/api/scans/{scan_id}/lime")
def lime_status(scan_id: int, wait: float = 0, user: auth.AuthUser = Depends(User)):
    """wait (seconds, max 25): long-poll until the job finishes or the wait ends.
    On Cloud Run a container only gets CPU while a request is open, so the UI
    keeps one of these open while LIME runs; that keeps the job progressing."""
    scan, _ = owned_scan(user, scan_id)
    st = lime_jobs.status(scan.image_path)
    deadline = time.monotonic() + max(0.0, min(wait, 25.0))
    while st["status"] in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.5)
        st = lime_jobs.status(scan.image_path)
    if st["status"] == "done":
        st["labels"] = services.lime_summary(scan.image_path)
    return st


@app.post("/api/scans/{scan_id}/lime", status_code=202)
def lime_start(scan_id: int, user: auth.AuthUser = Depends(User)):
    scan, _ = owned_scan(user, scan_id)
    require_model()
    return lime_jobs.start(scan.image_path)


@app.get("/api/scans/{scan_id}/lime/image")
def lime_image(scan_id: int, label: str, user: auth.AuthUser = Depends(User)):
    scan, _ = owned_scan(user, scan_id)
    data = services.lime_jpeg(scan.image_path, _label(label))
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LIME has not been run for this scan.")
    return image_response(data)


@app.get("/api/scans/{scan_id}/report.pdf")
def scan_report(scan_id: int, tz_offset_min: int = 0, user: auth.AuthUser = Depends(User)):
    """tz_offset_min: the browser's UTC offset, so report times match the clinician's clock."""
    from datetime import timedelta

    import report
    scan, patient = owned_scan(user, scan_id)
    tz = timezone(timedelta(minutes=max(-840, min(840, tz_offset_min))))
    local = db.as_utc(scan.created_at).astimezone(tz)
    pdf = services.report_pdf(scan, patient, user.display_name, local)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{report.filename(scan.id, local)}"',
        "Cache-Control": "no-store",
    })
