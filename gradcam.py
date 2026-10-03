"""Grad-CAM for the nested transfer-learning model + heatmap overlay.

Model shape (verified): outer Functional = [MobileNetV2 base (nested Functional)]
-> GlobalAveragePooling -> Dense(64, relu) -> Dropout -> Dense(1, sigmoid).

Approach (per docs/EXPLAINABILITY.md): a manual forward pass inside a
GradientTape instead of building one big `keras.Model(model.inputs, [conv, out])`.
Reaching into a nested model's layers from the outer model's inputs is what
causes graph-disconnected / duplicate-layer-name errors, so we:
  1. run any outer layers before the base,
  2. run a sub-model of the base that returns (last conv activations, base output),
  3. run the outer head layers one by one on the base output,
all inside the tape, so gradients flow from the score back to the conv map.

Target score: the final Dense layer's pre-sigmoid logit z (+z for PNEUMONIA,
-z for NORMAL). Using the probability instead would give vanishing gradients
when the model is very sure (p≈0 or p≈1) — common with this model — producing
blank or noisy maps. The logit is monotonic in p, so it explains the same decision.

Honesty: the conv map is 7x7, upsampled to the image. It shows coarse regions
that drove the prediction, NOT lesion boundaries.
"""
import cv2
import numpy as np
from PIL import Image

PNEUMONIA = "PNEUMONIA"


class GradCamError(RuntimeError):
    pass


def _split_model(model):
    """-> (layers_before_base, feature_model, head_layers). Cached on the model object."""
    cached = getattr(model, "_gradcam_split", None)
    if cached is not None:
        return cached
    import keras

    # InputLayers are placeholders, not callable transforms; some saved models list them.
    layers = [l for l in model.layers if not isinstance(l, keras.layers.InputLayer)]
    base_idx = next((i for i, l in enumerate(layers) if isinstance(l, keras.Model)), None)
    if base_idx is None:
        raise GradCamError("Expected a nested base model (transfer-learning layout).")
    base = layers[base_idx]
    conv_layers = [l for l in base.layers if len(l.output.shape) == 4]
    if not conv_layers:
        raise GradCamError("No convolutional (4D) layer found in the base model.")
    target = conv_layers[-1]
    # Built entirely inside the base's own graph, so no cross-graph references.
    feature_model = keras.Model(base.inputs, [target.output, base.output])
    split = (layers[:base_idx], feature_model, layers[base_idx + 1:])
    model._gradcam_split = split
    return split


def compute_heatmap(model, x: np.ndarray, target_label: str) -> np.ndarray:
    """x: preprocessed (1,224,224,3). Returns a (h,w) float map in [0,1] at
    conv-feature resolution (7x7 here). All zeros = no positive evidence found."""
    import keras
    import tensorflow as tf

    pre, feature_model, head = _split_model(model)
    sign = 1.0 if target_label == PNEUMONIA else -1.0

    t = tf.convert_to_tensor(x, dtype=tf.float32)
    for layer in pre:
        t = layer(t, training=False)

    with tf.GradientTape() as tape:
        conv_out, h = feature_model(t, training=False)
        for layer in head[:-1]:
            h = layer(h, training=False)
        last = head[-1]
        if isinstance(last, keras.layers.Dense):
            # Pre-activation logit (see module docstring for why).
            score = tf.matmul(h, last.kernel) + last.bias
        else:
            score = last(h, training=False)
        score = sign * score[:, 0]

    grads = tape.gradient(score, conv_out)
    if grads is None:
        raise GradCamError("Gradients could not be computed for this model.")

    weights = tf.reduce_mean(grads, axis=(1, 2))                 # (1, C): channel importance
    cam = tf.reduce_sum(conv_out * weights[:, None, None, :], axis=-1)[0]
    cam = tf.nn.relu(cam).numpy()                                # keep positive evidence only
    peak = cam.max()
    return cam / peak if peak > 0 else cam


def overlay(image: Image.Image, heatmap: np.ndarray, opacity: float) -> Image.Image:
    """Blend a JET-coloured heatmap over the X-ray. opacity 0 = X-ray only, 1 = heatmap only."""
    base = np.array(image.convert("RGB"))
    h, w = base.shape[:2]
    # Bilinear upsampling of the coarse map; smooth on purpose (it IS coarse).
    hm = cv2.resize(heatmap.astype("float32"), (w, h), interpolation=cv2.INTER_LINEAR)
    coloured = cv2.applyColorMap(np.uint8(255 * np.clip(hm, 0, 1)), cv2.COLORMAP_JET)
    coloured = cv2.cvtColor(coloured, cv2.COLOR_BGR2RGB)
    blended = cv2.addWeighted(base, 1.0 - opacity, coloured, opacity, 0)
    return Image.fromarray(blended)
