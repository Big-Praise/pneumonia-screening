import numpy as np
import pytest
from PIL import Image

import config
import lime_explain as L
from mock_predictor import MockPredictor


@pytest.fixture
def img():
    rng = np.random.default_rng(3)
    return Image.fromarray(rng.integers(0, 255, (256, 256), dtype=np.uint8))


def test_lime_predict_shape_and_rows_sum_to_one():
    fn = L.lime_predict_fn(MockPredictor())
    for scale in (1.0, 255.0):  # LIME may pass 0..1 or 0..255
        out = fn(np.random.default_rng(0).random((5, 224, 224, 3)) * scale)
        assert out.shape == (5, 2)
        assert np.allclose(out.sum(axis=1), 1.0)


def test_compute_mask_and_cache_roundtrip(img, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    r = L.compute(MockPredictor(), img, num_samples=30)
    assert r["segments"].shape == (224, 224)
    assert set(r["weights"]) == {0, 1}

    for label in ("NORMAL", "PNEUMONIA"):
        m = L.mask_for(r, label)
        assert m.shape == (224, 224) and m.dtype == bool
        n_regions = len(np.unique(r["segments"][m]))
        assert n_regions <= L.TOP_FEATURES

    assert L.load_cached("abc.png") is None
    L.save_cached("abc.png", r)
    back = L.load_cached("abc.png")
    assert np.array_equal(back["segments"], r["segments"])
    assert np.array_equal(L.mask_for(back, "PNEUMONIA"), L.mask_for(r, "PNEUMONIA"))
    assert back["num_samples"] == 30


def test_mask_ignores_negative_weights():
    r = {"segments": np.array([[0, 1], [2, 3]]),
         "weights": {0: [(0, -0.5), (1, -0.1)], 1: [(2, 0.3), (3, -0.2)]}}
    assert not L.mask_for(r, "NORMAL").any()
    assert L.mask_for(r, "PNEUMONIA").tolist() == [[False, False], [True, False]]
    assert L.top_weight(r, "PNEUMONIA") == pytest.approx(0.3)


def test_agreement():
    hm = np.zeros((7, 7)); hm[:3, :3] = 1.0          # hot top-left
    mask = np.zeros((224, 224), bool)
    assert L.agreement(hm, mask) is None
    mask[:40, :40] = True                              # LIME also top-left
    assert L.agreement(hm, mask) > 0.8
    mask[:] = False; mask[-40:, -40:] = True           # LIME bottom-right
    assert L.agreement(hm, mask) < 0.2


def test_overlay_size(img):
    m = np.zeros((224, 224), bool); m[50:100, 50:100] = True
    assert L.overlay(img, m).size == img.size
