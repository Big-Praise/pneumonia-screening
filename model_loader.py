"""Load the trained model (or the mock) behind one small predictor interface.

Every predictor exposes:
    is_demo        True only for the mock
    source         human-readable description for the UI
    keras_model    the underlying Keras model (None for the mock)
    predict_prob(batch) -> (N,) pneumonia probabilities, batch (N,224,224,3) in [0,1]

Real vs mock is decided by whether the model file exists (config.MODEL_CANDIDATES).
To force demo mode for testing, change the one line in load_predictor() marked SWAP.

Caching is done by the caller (app.py wraps load_predictor in st.cache_resource)
so this module stays importable and testable without Streamlit.
"""
from pathlib import Path

import numpy as np

import config
from mock_predictor import MockPredictor


class ModelLoadError(RuntimeError):
    """The model file exists but could not be loaded. Never silently fall back."""


class KerasPredictor:
    is_demo = False

    def __init__(self, path: Path):
        # Imported here so the mock path (and the test suite) doesn't pay
        # TensorFlow's multi-second import cost.
        import keras
        import tensorflow as tf

        # compile=False: inference only. Skips restoring optimizer state, which
        # is irrelevant here and triggers a harmless-but-noisy warning.
        self.keras_model = keras.models.load_model(path, compile=False)
        # Warm-up call so every layer is built before Grad-CAM walks them.
        self.keras_model(tf.zeros((1, 224, 224, 3)))
        self.source = path.name

    def predict_prob(self, batch: np.ndarray) -> np.ndarray:
        batch = np.asarray(batch, dtype="float32")
        if len(batch) <= 8:
            # Direct call avoids predict()'s per-call setup overhead for single images.
            out = self.keras_model(batch, training=False)
        else:
            out = self.keras_model.predict(batch, batch_size=32, verbose=0)
        return np.asarray(out, dtype=float).reshape(-1)


def find_model_file() -> Path | None:
    return next((p for p in config.MODEL_CANDIDATES if p.exists()), None)


def load_predictor():
    """Real model if the file is present, else the mock. Raises ModelLoadError
    if the file is present but broken — showing fake results instead would
    violate GUARDRAILS ("never fabricate results")."""
    path = find_model_file()  # SWAP: replace with `path = None` to force demo mode
    if path is None:
        return MockPredictor()
    try:
        return KerasPredictor(path)
    except Exception as e:  # noqa: BLE001 — surface any load failure honestly
        raise ModelLoadError(f"Could not load {path.name}: {e}") from e
