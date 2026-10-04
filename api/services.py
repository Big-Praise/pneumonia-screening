"""Model state, explanation caching, LIME background jobs and PDF assembly for the API.

Decisions:
- The model loads in a background thread at startup, so the server answers
  health checks immediately (hosts kill containers that don't respond) and
  the UI can show "model loading" instead of hanging.
- LIME takes 1-3 minutes on a CPU host: longer than proxy/request timeouts. It
  runs as a background job (one at a time — they're CPU-bound) and the browser
  polls for progress. Results go to the blob store, so they survive restarts.
"""
import io
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache

import numpy as np
from PIL import Image

import config
import gradcam
import lime_explain
import model_loader
import predict
import report
import storage

log = logging.getLogger("api")

DISPLAY_PX = 1024
THUMB_PX = 160


# ------------------------------------------------------------------ model state

class ModelState:
    def __init__(self):
        self.predictor = None
        self.error: str | None = None
        self.loading = False
        self._lock = threading.Lock()

    def start_loading(self) -> None:
        with self._lock:
            if self.loading or self.predictor is not None:
                return
            self.loading = True
        threading.Thread(target=self._load, name="model-loader", daemon=True).start()

    def _load(self) -> None:
        try:
            self.predictor = model_loader.load_predictor()
            log.info("Model ready: %s", self.predictor.source)
        except model_loader.ModelLoadError as e:
            self.error = str(e)
            log.error("Model failed to load: %s", e)
        finally:
            self.loading = False

    def status(self) -> dict:
        if self.predictor is not None:
            return {"status": "demo" if self.predictor.is_demo else "ready",
                    "source": self.predictor.source, "error": None}
        if self.error:
            return {"status": "error", "source": None, "error": self.error}
        return {"status": "loading", "source": None, "error": None}


model = ModelState()


# ------------------------------------------------------------------ images

def _jpeg(img: Image.Image, quality: int = 88) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def resized(img: Image.Image, px: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((px, px))
    return img


@lru_cache(maxsize=32)
def display_image(image_rel: str) -> Image.Image:
    return resized(storage.open_image(image_rel), DISPLAY_PX)


def image_jpeg(image_rel: str, px: int) -> bytes:
    return _jpeg(resized(display_image(image_rel), px))


@lru_cache(maxsize=128)
def heatmap(image_rel: str, label: str) -> np.ndarray:
    x = predict.preprocess(storage.open_image(image_rel))
    return gradcam.compute_heatmap(model.predictor.keras_model, x, label)


def gradcam_jpeg(image_rel: str, label: str) -> bytes:
    """The coloured heatmap alone, sized like the display image. The browser lays
    it over the X-ray with CSS opacity, so the opacity slider needs no server call."""
    base = display_image(image_rel)
    return _jpeg(gradcam.overlay(base, heatmap(image_rel, label), 1.0), quality=85)


# ------------------------------------------------------------------ LIME jobs

class _Counting:
    """Wraps a predictor to count images LIME has evaluated -> progress %."""
    def __init__(self, inner, total: int, on_progress):
        self.inner, self.total, self.done, self.on_progress = inner, total, 0, on_progress
        self.is_demo, self.source = inner.is_demo, inner.source

    def predict_prob(self, batch):
        out = self.inner.predict_prob(batch)
        self.done += len(batch)
        self.on_progress(min(self.done / self.total, 0.99))
        return out


class LimeJobs:
    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lime")
        self._state: dict[str, dict] = {}
        self._lock = threading.Lock()

    def status(self, image_rel: str) -> dict:
        with self._lock:
            st = self._state.get(image_rel)
        if st and st["status"] in ("queued", "running", "error"):
            return dict(st)
        if lime_explain.has_cached(image_rel):
            return {"status": "done", "progress": 1.0}
        return {"status": "none", "progress": 0.0}

    def start(self, image_rel: str) -> dict:
        current = self.status(image_rel)
        if current["status"] in ("queued", "running", "done"):
            return current
        with self._lock:
            self._state[image_rel] = {"status": "queued", "progress": 0.0}
        self._pool.submit(self._run, image_rel)
        return self.status(image_rel)

    def _set(self, image_rel: str, **kw) -> None:
        with self._lock:
            self._state.setdefault(image_rel, {}).update(kw)

    def _run(self, image_rel: str) -> None:
        self._set(image_rel, status="running", progress=0.0)
        try:
            counting = _Counting(model.predictor, config.LIME_NUM_SAMPLES + 1,
                                 lambda p: self._set(image_rel, progress=p))
            result = lime_explain.compute(counting, storage.open_image(image_rel),
                                          num_samples=config.LIME_NUM_SAMPLES)
            lime_explain.save_cached(image_rel, result)
            with self._lock:
                self._state.pop(image_rel, None)  # "done" now comes from the cache
        except Exception:  # noqa: BLE001 — reported to the UI as an honest error
            log.exception("LIME failed")
            self._set(image_rel, status="error", progress=0.0)


lime_jobs = LimeJobs()


def lime_summary(image_rel: str) -> dict | None:
    """Per-label facts for the UI: weak evidence + agreement with Grad-CAM."""
    res = lime_explain.load_cached(image_rel)
    if res is None:
        return None
    out = {}
    for label in (predict.NORMAL, predict.PNEUMONIA):
        mask = lime_explain.mask_for(res, label)
        try:
            agree = lime_explain.agreement(heatmap(image_rel, label), mask)
        except Exception:  # noqa: BLE001
            agree = None
        out[label] = {
            "has_regions": bool(mask.any()),
            "weak": lime_explain.top_weight(res, label) < lime_explain.WEAK_WEIGHT,
            "agreement": agree,
        }
    return out


def lime_jpeg(image_rel: str, label: str) -> bytes | None:
    res = lime_explain.load_cached(image_rel)
    if res is None:
        return None
    return _jpeg(lime_explain.overlay(display_image(image_rel), lime_explain.mask_for(res, label)))


# ------------------------------------------------------------------ PDF

def report_pdf(scan, patient, clinician: str, scan_time: datetime) -> bytes:
    """PDF for the SAVED record (label/confidence/threshold as stored)."""
    original = resized(display_image(scan.image_path), 640)
    label = scan.predicted_label
    try:
        hm = heatmap(scan.image_path, label)
        cam = gradcam.overlay(original, hm, 0.45)
    except Exception:  # noqa: BLE001 — the report says "unavailable" rather than faking it
        hm, cam = None, None
    lime_img, weak, agree = None, False, None
    res = lime_explain.load_cached(scan.image_path)
    if res is not None:
        mask = lime_explain.mask_for(res, label)
        lime_img = lime_explain.overlay(original, mask)
        weak = lime_explain.top_weight(res, label) < lime_explain.WEAK_WEIGHT
        agree = lime_explain.agreement(hm, mask) if hm is not None else None
    p = model.predictor
    return report.build_pdf(report.ReportData(
        scan_id=scan.id, scan_time=scan_time, patient_name=patient.name,
        patient_age=patient.age, patient_sex=patient.sex, clinician=clinician,
        label=label, confidence=scan.confidence, pneumonia_prob=scan.pneumonia_prob,
        threshold=scan.threshold_used, model_source=p.source if p else "model not loaded",
        is_demo=bool(p and p.is_demo), original=original, gradcam=cam, lime=lime_img,
        lime_weak=weak, agreement=agree,
    ))
