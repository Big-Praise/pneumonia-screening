# Model Interface — loading and calling the trained model

Contract between the app and the trained model. Follow exactly.

### The model file
- Name: `pneumonia_model.keras` (Keras format; may also be a `.h5` — handle both).
- Location: project root.
- May be ABSENT at first — then use `mock_predictor.py` and show a DEMO MODE
  banner. Swapping to the real model must be a one-line change.

### Loading (cache it)
```python
import tensorflow as tf
from tensorflow import keras
import streamlit as st

@st.cache_resource
def get_model():
    m = keras.models.load_model("pneumonia_model.keras")
    # warm up so all layers are built before Grad-CAM uses them
    import numpy as np
    m(tf.zeros((1, 224, 224, 3)))
    return m
```

### Preprocessing (MUST match training)
- Convert to RGB, resize to **224x224**, rescale by **1/255.0**, add batch dim.
```python
import numpy as np
def preprocess(pil_image):
    img = pil_image.convert("RGB").resize((224, 224))
    arr = np.array(img, dtype="float32") / 255.0
    return np.expand_dims(arr, 0)   # (1,224,224,3)
```

### Output interpretation
- Final layer = single sigmoid -> probability of PNEUMONIA (class order:
  NORMAL=0, PNEUMONIA=1, alphabetical from the training generator).
- `p = model.predict(x)[0][0]`
- With a threshold T (from the slider, default 0.5):
  - label = "PNEUMONIA" if p >= T else "NORMAL"
  - confidence = p if label=="PNEUMONIA" else (1 - p)

### LIME predict function
LIME needs a function that takes a batch of images (H,W,3 in 0..255 or 0..1) and
returns class probabilities for BOTH classes. Wrap the model so it returns a
2-column array [[prob_normal, prob_pneumonia], ...]:
```python
def lime_predict(images):   # images: (N,224,224,3)
    x = images.astype("float32")
    if x.max() > 1.5:       # if 0..255, rescale
        x = x / 255.0
    p = get_model().predict(x).flatten()       # prob pneumonia
    return np.stack([1 - p, p], axis=1)        # [normal, pneumonia]
```

### Grad-CAM target
- Target the last 4D (convolutional) layer. Keep the existing manual
  forward-pass implementation that avoids duplicate-layer-name errors.

### Hard rules
- Do NOT retrain or modify the model.
- Do NOT change preprocessing — it must match training.
- Verify class order against the training `class_indices` if predictions ever
  look inverted.
