"""LIME explanation (lime_image) for one X-ray, plus on-disk caching per scan.

How LIME works (for comments + the report): it splits the image into
superpixels, makes many copies with random groups of superpixels greyed out,
runs the model on every copy, then fits a simple linear model to learn which
superpixels most move the prediction. The top positive superpixels are shown.

Decisions:
- One run explains BOTH classes (labels=(0, 1)), and we store the superpixel
  map + per-class weights, not a picture. So when the threshold slider flips
  the label, the other class's explanation is already there — no rerun.
- Cached as .npz in the blob store (disk or DB), keyed by the stored
  image name. Survives restarts, so history and the PDF reuse it.
- Fixed random_state: the same scan always gets the same explanation.
"""
import io
from pathlib import Path

import numpy as np
from PIL import Image

import blobstore
import config
import predict

CLASS_INDEX = {predict.NORMAL: 0, predict.PNEUMONIA: 1}
TOP_FEATURES = 5      # superpixels highlighted
N_SEGMENTS = 50       # ~50 SLIC superpixels on a 224x224 image
RANDOM_STATE = 0


def lime_predict_fn(predictor):
    """Wrap the predictor in LIME's contract: (N,H,W,3) -> (N,2) [normal, pneumonia]."""
    def fn(images: np.ndarray) -> np.ndarray:
        x = images.astype("float32")
        if x.max() > 1.5:  # LIME may hand back 0..255
            x = x / 255.0
        p = predictor.predict_prob(x)
        return np.stack([1.0 - p, p], axis=1)
    return fn


def compute(predictor, pil_image: Image.Image, num_samples: int = config.LIME_NUM_SAMPLES) -> dict:
    """Run LIME once. Returns {'segments', 'weights': {0: [...], 1: [...]}, 'num_samples'}."""
    from lime import lime_image
    from lime.wrappers.scikit_image import SegmentationAlgorithm

    x = predict.preprocess(pil_image)[0].astype("double")  # (224,224,3) in [0,1] — model's own input
    # SLIC gives compact, roughly equal superpixels; on grey X-rays the default
    # quickshift tends to make a few huge irregular blobs.
    segmenter = SegmentationAlgorithm("slic", n_segments=N_SEGMENTS, compactness=10,
                                      sigma=1, start_label=0, channel_axis=-1)
    explainer = lime_image.LimeImageExplainer(random_state=RANDOM_STATE)
    exp = explainer.explain_instance(
        x, lime_predict_fn(predictor), labels=(0, 1), top_labels=None,
        # hide_color=None: a "removed" superpixel becomes its own mean brightness.
        # Black (0) would mimic air on an X-ray — i.e. inject a fake "clear lung"
        # signal — and distorts the explanation.
        hide_color=None, num_samples=num_samples, batch_size=64,
        segmentation_fn=segmenter, random_seed=RANDOM_STATE,
    )
    return {
        "segments": exp.segments.astype(np.int32),
        "weights": {k: [(int(s), float(w)) for s, w in exp.local_exp[k]] for k in (0, 1)},
        "num_samples": num_samples,
    }


WEAK_WEIGHT = 0.02  # below this, removing the best region shifts p by <~2 points


def top_weight(result: dict, label: str) -> float:
    weights = result["weights"][CLASS_INDEX[label]]
    return max((w for _, w in weights), default=0.0)


def mask_for(result: dict, label: str, top: int = TOP_FEATURES) -> np.ndarray:
    """Boolean (224,224) mask of the top superpixels supporting `label` (positive weights only)."""
    weights = result["weights"][CLASS_INDEX[label]]
    keep = [s for s, w in sorted(weights, key=lambda sw: -sw[1])[:top] if w > 0]
    return np.isin(result["segments"], keep)


def overlay(image: Image.Image, mask: np.ndarray) -> Image.Image:
    """Tint the supporting superpixels and outline them, on a display-size image."""
    from skimage.segmentation import mark_boundaries

    base = np.asarray(image.convert("RGB"), dtype="float32") / 255.0
    h, w = base.shape[:2]
    m = np.array(Image.fromarray(mask.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)) > 0
    tint = np.array([0.10, 0.75, 0.55])  # green-teal: distinct from Grad-CAM's jet colours
    out = base.copy()
    out[m] = 0.55 * base[m] + 0.45 * tint
    out = mark_boundaries(out, m.astype(int), color=(0.0, 0.55, 0.45), mode="thick")
    return Image.fromarray(np.uint8(np.clip(out, 0, 1) * 255))


def agreement(heatmap: np.ndarray, mask: np.ndarray) -> float | None:
    """Rough overlap between Grad-CAM's hottest area and LIME's regions:
    share of LIME's highlighted area that falls in the equally-sized hottest
    Grad-CAM area. None if LIME highlighted nothing."""
    import cv2

    area = mask.mean()
    if area == 0:
        return None
    hm = cv2.resize(heatmap.astype("float32"), mask.shape[::-1], interpolation=cv2.INTER_LINEAR)
    hot = hm >= np.quantile(hm, 1.0 - area)
    return float((hot & mask).sum() / mask.sum())


# ------------------------------------------------------------------ cache
# Stored via blobstore (disk or DB) as "lime/<image stem>.npz", so it survives
# restarts and history/PDF reuse it.

def cache_name(image_rel: str) -> str:
    return f"lime/{Path(image_rel).stem}.npz"


def load_cached(image_rel: str) -> dict | None:
    data = blobstore.get(cache_name(image_rel))
    if data is None:
        return None
    with np.load(io.BytesIO(data)) as z:
        return {
            "segments": z["segments"],
            "weights": {0: [tuple(r) for r in z["w0"].tolist()],
                        1: [tuple(r) for r in z["w1"].tolist()]},
            "num_samples": int(z["num_samples"]),
        }


def has_cached(image_rel: str) -> bool:
    return blobstore.exists(cache_name(image_rel))


def save_cached(image_rel: str, result: dict) -> None:
    buf = io.BytesIO()
    np.savez_compressed(
        buf, segments=result["segments"],
        w0=np.array(result["weights"][0]), w1=np.array(result["weights"][1]),
        num_samples=result["num_samples"],
    )
    blobstore.put(cache_name(image_rel), buf.getvalue())
