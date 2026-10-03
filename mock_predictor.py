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
    keras_model = None  # Grad-CAM needs a real network; see model_loader

    def predict_prob(self, batch: np.ndarray) -> np.ndarray:
        """batch: (N,224,224,3) floats in [0,1] -> (N,) fake pneumonia probabilities."""
        out = []
        for img in batch:
            # Same image -> same number, so reruns are stable.
            seed = int.from_bytes(hashlib.sha256(img.tobytes()).digest()[:4], "little")
            out.append(np.random.default_rng(seed).uniform(0.05, 0.95))
        return np.asarray(out, dtype=float)
