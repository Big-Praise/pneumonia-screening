# Explainability Spec — Grad-CAM, LIME, and the sliders

The result screen must make the model's decision transparent in three ways.

## 1. Grad-CAM (already have the logic — port it)
- Computes a heatmap from the last convolutional layer's gradients w.r.t. the
  predicted class; highlights the lung regions that most drove the prediction.
- Port the existing working implementation. Note it uses a manual layer-by-layer
  forward pass inside a gradient tape to avoid duplicate-layer-name errors in the
  nested transfer-learning model — keep that approach.
- Output: a heatmap overlaid on the X-ray.

## 2. LIME (NEW — an addition to Grad-CAM, not a replacement)
- Uses the `lime` library's `lime_image.LimeImageExplainer`.
- How it works (for comments + the report): LIME segments the image into
  superpixels, turns groups of them on/off to create perturbed variants, runs
  the model on each, and learns which superpixels most affect the prediction.
  It then highlights those regions.
- Use `explain_instance(image, model_predict_fn, ...)` then
  `get_image_and_mask(label, positive_only=True, hide_rest=False)` to get the
  highlighted regions; display that next to the Grad-CAM view.
- The framing to support in the UI/report: Grad-CAM and LIME are two independent
  methods; when they agree on the same region, confidence in the explanation is
  higher. Show them side by side.
- PERFORMANCE: LIME is slow (it perturbs the image many times). Therefore:
  - Run LIME on a button/toggle ("Show LIME explanation"), not automatically.
  - Keep `num_samples` modest (e.g. ~1000) so the demo stays responsive.
  - Show a spinner; cache the LIME result for that scan so it isn't recomputed.

## 3. Interactive sliders (NEW)
- **Confidence-threshold slider** (0.0–1.0, default 0.5): the model outputs a
  pneumonia probability p. The displayed label is PNEUMONIA if p >= threshold,
  else NORMAL. Moving the slider updates the label live. Lower threshold = more
  sensitive (catches more pneumonia, more false alarms); higher = stricter.
  Show a one-line explanation of this trade-off near the slider. Save the
  threshold used with the scan.
- **Heatmap-opacity slider** (0.0–1.0, default ~0.4): blends the Grad-CAM heatmap
  over the original X-ray so the clinician can fade it in/out to see the anatomy
  underneath.

## Honesty note (ties to GUARDRAILS)
- Heatmaps are coarse (upsampled from a low-resolution feature map) — do not
  present them as precise lesion boundaries.
- The sliders change how results are displayed/interpreted; they do not change
  the model. Make that clear so no one thinks moving a slider "improves" the AI.
