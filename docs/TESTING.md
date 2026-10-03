# Testing — v2

Keep logic in pure, testable functions; verify each milestone manually.

## Per-milestone acceptance
- M0: app boots to login + disclaimer.
- M1: register + login + logout work; password stored as a hash (check the DB
  row is NOT plaintext); tables exist.
- M2: create patient, upload, mock prediction, Scan row saved, image in uploads/.
- M3: real prediction + Grad-CAM; opacity slider blends live.
- M4: threshold slider flips the label at the cutoff; threshold_used saved.
- M5: LIME renders beside Grad-CAM; runs on toggle with a spinner; cached.
- M6: history lists and reopens saved scans for a patient.
- M7: PDF downloads with prediction, confidence, heatmap, disclaimer.
- M8: friendly errors on bad input; clean run from README.

## Logic sanity checks (pure functions)
- preprocess() -> (1,224,224,3), values in [0,1].
- predict() with threshold 0.5 -> label in {NORMAL,PNEUMONIA}, confidence in
  [0.5,1.0].
- lime_predict() -> shape (N,2), rows sum to ~1.
- Class-order regression: on a known PNEUMONIA sample, p should be high; if
  predictions look inverted, re-check class_indices first.

## Security checks
- Passwords never stored or logged in plaintext.
- No secrets hard-coded (grep the repo).
- No network calls during inference (model runs locally).
