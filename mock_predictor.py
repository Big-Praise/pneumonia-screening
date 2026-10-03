"""Stand-in predictor used ONLY when pneumonia_model.keras is absent.

Its output is not a medical result: it's a deterministic pseudo-random number
derived from the image bytes, so the app can run end-to-end for development.
The UI shows a DEMO MODE banner whenever this is active.
"""
import hashlib

import numpy as np


class MockPredictor:
    is_demo = True
    source = "mock predictor (no model file found)"

    def __init__(self):
        self._keras_model = None

    @property
    def keras_model(self):
        """A tiny UNTRAINED network with the same nested layout as the real model,
        so the Grad-CAM/LIME code paths can be exercised in demo mode. Its heatmaps
        are meaningless and the UI labels them DEMO. Built lazily so demo mode
        doesn't pay for TensorFlow until an explanation is requested."""
        if self._keras_model is None:
            import keras

            keras.utils.set_random_seed(0)
            # Functional (not Sequential) base, matching MobileNetV2, so Grad-CAM can
            # build its sub-model from base.inputs.
            b_in = keras.Input((224, 224, 3))
            b = keras.layers.Conv2D(8, 3, strides=4, activation="relu")(b_in)
            b = keras.layers.Conv2D(16, 3, strides=4, activation="relu")(b)
            base = keras.Model(b_in, b, name="demo_base")
            inp = keras.Input((224, 224, 3))
            h = keras.layers.GlobalAveragePooling2D()(base(inp))
            out = keras.layers.Dense(1, activation="sigmoid")(h)
            self._keras_model = keras.Model(inp, out, name="demo_untrained")
        return self._keras_model

    def predict_prob(self, batch: np.ndarray) -> np.ndarray:
        """batch: (N,224,224,3) floats in [0,1] -> (N,) fake pneumonia probabilities."""
        out = []
        for img in batch:
            # Same image -> same number, so reruns are stable.
            seed = int.from_bytes(hashlib.sha256(img.tobytes()).digest()[:4], "little")
            out.append(np.random.default_rng(seed).uniform(0.05, 0.95))
        return np.asarray(out, dtype=float)
