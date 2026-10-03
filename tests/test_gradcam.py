"""Grad-CAM tests run on the untrained demo network (same nested layout as the
real model) so they don't depend on pneumonia_model.keras being present."""
import numpy as np
import pytest
from PIL import Image

import gradcam
import predict
from mock_predictor import MockPredictor


@pytest.fixture(scope="module")
def demo_model():
    return MockPredictor().keras_model


def test_heatmap_shape_and_range(demo_model):
    x = predict.preprocess(Image.fromarray(np.random.default_rng(1).integers(0, 255, (256, 256), dtype=np.uint8)))
    for label in ("PNEUMONIA", "NORMAL"):
        hm = gradcam.compute_heatmap(demo_model, x, label)
        assert hm.ndim == 2
        assert hm.min() >= 0 and hm.max() <= 1


def test_overlay_opacity_extremes():
    img = Image.new("L", (100, 80), 100)
    hm = np.ones((7, 7), dtype="float32")
    assert np.array_equal(np.array(gradcam.overlay(img, hm, 0.0)), np.array(img.convert("RGB")))
    full = np.array(gradcam.overlay(img, hm, 1.0))
    assert full.shape == (80, 100, 3)
    assert not np.array_equal(full, np.array(img.convert("RGB")))


def test_flat_model_rejected():
    import keras
    inp = keras.Input((224, 224, 3))
    out = keras.layers.Dense(1)(keras.layers.GlobalAveragePooling2D()(keras.layers.Conv2D(2, 3)(inp)))
    with pytest.raises(gradcam.GradCamError):
        gradcam.compute_heatmap(keras.Model(inp, out), np.zeros((1, 224, 224, 3), "float32"), "NORMAL")
