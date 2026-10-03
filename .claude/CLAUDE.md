# CLAUDE.md — Pneumonia Screening App (Full-Stack v2)

Short, always-loaded rules. Detail lives in docs/ and .claude/skills/. Keep lean.

## What this is
Full-stack clinical decision-support app around a trained chest X-ray classifier.
Login -> upload X-ray for a patient -> prediction + confidence + Grad-CAM + LIME
+ sliders -> saved to a database -> viewable history -> exportable PDF.
Decision-support, NOT diagnosis.

## Read first
- docs/PRD.md = source of truth for scope.
- docs/GUARDRAILS.md = non-negotiable (medical safety + data privacy).
- docs/BUILD_PLAN.md = milestone order; build one at a time, run, show, wait.
- docs/MODEL_INTERFACE.md = exact model load/call contract.
- docs/DATA_MODEL.md = DB schema. docs/EXPLAINABILITY.md = Grad-CAM/LIME/sliders.

## Hard rules
- Never output "diagnosis"/"diagnosed"/"confirmed"/"you have pneumonia".
- Medical disclaimer visible on every screen.
- Never send images/patient data to an external API. Inference is local.
- Passwords: bcrypt hashes only, never plaintext, never logged.
- Dev data: fake patient names + the project's sample X-rays only.
- No secrets hard-coded. Use env vars / config with `# TODO (Praise)` marks —
  the user (Praise) handles auth secrets and final connecting.
- Do not retrain the model or change preprocessing (224x224, /255).
- If real model absent -> mock + DEMO MODE banner; swap is one line.

## Stack
Path A default: Streamlit + SQLite + SQLAlchemy + passlib/bcrypt;
TensorFlow/Keras + Pillow + OpenCV (Grad-CAM); lime + scikit-image (LIME);
reportlab (PDF). Confirm Path A vs B before building. See docs/TECH_STACK.md.

## Workflow
- Summarise the plan + any pushback before coding; wait for confirmation.
- Keep UI in app.py; data in db.py/auth.py; ML in predict/gradcam/lime_explain.
- LIME is slow — run on a toggle, spinner, cache per scan, modest num_samples.
- Run the app after each change set; never leave it broken.
- Comment non-obvious code; explain decisions in a sentence. The user ships fast
  and wants pushback, not blind agreement.

## Commands
- Run: `streamlit run app.py`   • Install: `pip install -r requirements.txt`

## When corrected
Add a one-line rule here so it isn't repeated.
