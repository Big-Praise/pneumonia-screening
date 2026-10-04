import io
import re
from datetime import datetime

import numpy as np
import pytest
from PIL import Image

import report

BANNED = re.compile(r"\b(diagnosed|confirmed|you have pneumonia)\b", re.I)


def _data(**kw):
    img = Image.fromarray(np.random.default_rng(0).integers(0, 255, (300, 300), dtype=np.uint8))
    base = dict(
        scan_id=7, scan_time=datetime(2026, 10, 4, 14, 30), patient_name="Test Patient Bello",
        patient_age=34, patient_sex="Male", clinician="Dr Amaka Test", label="PNEUMONIA",
        confidence=0.772, pneumonia_prob=0.772, threshold=0.5, model_source="pneumonia_model.keras",
        is_demo=False, original=img, gradcam=img.convert("RGB"), lime=img.convert("RGB"),
        lime_weak=True, agreement=0.26,
    )
    base.update(kw)
    return report.ReportData(**base)


def _text(pdf: bytes) -> str:
    """Extract text with pypdf if available, else skip text assertions."""
    pypdf = pytest.importorskip("pypdf")
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)


def test_pdf_is_valid_and_contains_key_facts():
    pdf = report.build_pdf(_data())
    assert pdf.startswith(b"%PDF") and len(pdf) > 5_000
    text = _text(pdf)
    for needle in ["Test Patient Bello", "likely", "PNEUMONIA", "77%", "0.772", "0.50",
                   "not a diagnosis", "Known limitations", "Dr Amaka Test", "partial"]:
        assert needle in text, needle
    assert not BANNED.search(text)


def test_pdf_without_lime_or_gradcam_and_demo_flag():
    text = _text(report.build_pdf(_data(lime=None, gradcam=None, agreement=None, is_demo=True,
                                        label="NORMAL", confidence=0.4, pneumonia_prob=0.6,
                                        threshold=0.7)))
    assert "LIME was not run" in text
    assert "Grad-CAM unavailable" in text
    assert "DEMO MODE" in text
    assert "borderline" in text            # confidence < 0.5 note


def test_filename_has_no_patient_name():
    name = report.filename(7, datetime(2026, 10, 4))
    assert name == "screening_report_scan7_20261004.pdf"
