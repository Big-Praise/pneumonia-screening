import io

import numpy as np
import pytest
from PIL import Image

import auth
import config
import db
import predict
import storage
from mock_predictor import MockPredictor


def _png_bytes(size=(300, 300), mode="L", fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, 128).save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------- predict

def test_preprocess_shape_and_range():
    x = predict.preprocess(Image.new("L", (500, 400), 255))
    assert x.shape == (1, 224, 224, 3)
    assert x.dtype == np.float32
    assert 0.0 <= x.min() and x.max() <= 1.0


@pytest.mark.parametrize("p,t,label,conf", [
    (0.80, 0.5, "PNEUMONIA", 0.80),
    (0.20, 0.5, "NORMAL", 0.80),
    (0.50, 0.5, "PNEUMONIA", 0.50),   # p == threshold -> PNEUMONIA (>=)
    (0.30, 0.25, "PNEUMONIA", 0.30),  # lower threshold flips the label
])
def test_classify(p, t, label, conf):
    got_label, got_conf = predict.classify(p, t)
    assert got_label == label
    assert got_conf == pytest.approx(conf)


def test_default_threshold_confidence_at_least_half():
    for p in np.linspace(0, 1, 21):
        label, conf = predict.classify(p, 0.5)
        assert label in {"NORMAL", "PNEUMONIA"} and 0.5 <= conf <= 1.0


def test_mock_is_deterministic_and_in_range():
    m = MockPredictor()
    x = predict.preprocess(Image.new("L", (300, 300), 90))
    assert m.predict_prob(x)[0] == m.predict_prob(x)[0]
    assert 0 <= m.predict_prob(x)[0] <= 1


# ---------------------------------------------------------------- storage

def test_upload_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    img = storage.load_upload(_png_bytes(fmt="JPEG"))
    rel = storage.save_image(img)
    assert rel.endswith(".png") and (tmp_path / rel).exists()
    assert storage.open_image(rel).size == (300, 300)


@pytest.mark.parametrize("data", [
    b"not an image at all",
    _png_bytes(size=(20, 20)),                 # too small
    _png_bytes()[:200],                         # truncated
])
def test_bad_uploads_rejected(data):
    with pytest.raises(storage.ImageError):
        storage.load_upload(data)


def test_path_traversal_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    with pytest.raises(storage.ImageError):
        storage.image_path("../app.db")


# ---------------------------------------------------------------- db scoping

def test_patients_and_scans_scoped_to_owner():
    a = auth.register_user("dr.a", "password-a")
    b = auth.register_user("dr.b", "password-b")
    pa = db.create_patient(a.id, "Test Patient A", 40, "Female")
    scan = db.create_scan(a.id, pa.id, "x.png", "NORMAL", 0.9, 0.1, 0.5)

    assert [p.name for p in db.list_patients(a.id)] == ["Test Patient A"]
    assert db.list_patients(b.id) == []
    assert db.recent_scans(b.id) == []
    with pytest.raises(db.NotFound):
        db.get_patient(b.id, pa.id)
    with pytest.raises(db.NotFound):
        db.get_scan(b.id, scan.id)
    with pytest.raises(db.NotFound):  # can't attach a scan to someone else's patient
        db.create_scan(b.id, pa.id, "y.png", "NORMAL", 0.9, 0.1, 0.5)

    s, p = db.get_scan(a.id, scan.id)
    assert (s.pneumonia_prob, s.threshold_used, p.name) == (0.1, 0.5, "Test Patient A")
    assert db.count_for_user(a.id) == (1, 1)


def test_update_threshold_recomputes_label_and_is_scoped():
    a = auth.register_user("dr.a", "password-a")
    b = auth.register_user("dr.b", "password-b")
    pa = db.create_patient(a.id, "Test Patient A")
    scan = db.create_scan(a.id, pa.id, "x.png", "PNEUMONIA", 0.6, 0.6, 0.5)

    updated = db.update_scan_threshold(a.id, scan.id, 0.7)  # p=0.6 < 0.7 -> NORMAL
    assert (updated.predicted_label, updated.threshold_used) == ("NORMAL", 0.7)
    assert updated.confidence == pytest.approx(0.4)
    s, _ = db.get_scan(a.id, scan.id)
    assert (s.predicted_label, s.threshold_used, s.pneumonia_prob) == ("NORMAL", 0.7, 0.6)

    with pytest.raises(db.NotFound):
        db.update_scan_threshold(b.id, scan.id, 0.3)
    with pytest.raises(ValueError):
        db.update_scan_threshold(a.id, scan.id, 1.5)


def test_patient_validation():
    a = auth.register_user("dr.a", "password-a")
    with pytest.raises(ValueError):
        db.create_patient(a.id, "   ")
    with pytest.raises(ValueError):
        db.create_patient(a.id, "Someone", age=200)
