"""Preprocess -> infer -> (label, confidence). Pure functions; see docs/MODEL_INTERFACE.md.

Preprocessing MUST match training: RGB, 224x224, /255. Do not change it.
"""
import numpy as np
from PIL import Image

NORMAL, PNEUMONIA = "NORMAL", "PNEUMONIA"  # class order: NORMAL=0, PNEUMONIA=1
IMG_SIZE = (224, 224)


def preprocess(pil_image: Image.Image) -> np.ndarray:
    img = pil_image.convert("RGB").resize(IMG_SIZE)
    arr = np.array(img, dtype="float32") / 255.0
    return np.expand_dims(arr, 0)  # (1,224,224,3)


def classify(p: float, threshold: float) -> tuple[str, float]:
    """Label from pneumonia probability p and threshold T.
    Confidence is the probability of the label shown (p or 1-p)."""
    if p >= threshold:
        return PNEUMONIA, float(p)
    return NORMAL, float(1.0 - p)


def pneumonia_probability(predictor, pil_image: Image.Image) -> float:
    return float(predictor.predict_prob(preprocess(pil_image))[0])
