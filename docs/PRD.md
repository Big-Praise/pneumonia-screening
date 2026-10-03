# Product Requirements Document — Pneumonia Screening App (Full-Stack v2)

## 1. Overview
Upgrade the existing demo (a Streamlit app that classifies a chest X-ray and
shows a Grad-CAM heatmap) into a **full-stack clinical decision-support tool**
with user login, a database that stores patients and their X-ray scans, richer
explainability (Grad-CAM + LIME + interactive sliders), per-patient history, and
exportable PDF reports.

The ML model is already trained (MobileNetV2, ~90% accuracy, ~96% pneumonia
recall). This project is the application + data layer around it. It remains
decision-support, NOT diagnosis.

## 2. What changed from v1 (the demo)
- v1 stored nothing. v2 stores patients, images, and results in a database.
- v1 had no users. v2 has clinician login; scans belong to the logged-in user.
- v1 had Grad-CAM only. v2 adds LIME, a confidence-threshold slider, and a
  heatmap-opacity slider.
- v1 showed one result. v2 keeps per-patient history and exports a PDF report.
- v1 ran via ngrok from Colab. v2 targets a deployable full-stack app.

## 3. Goals
- G1. A clinician logs in and uploads a chest X-ray for a named patient.
- G2. The app predicts NORMAL/PNEUMONIA with a confidence score.
- G3. The app shows Grad-CAM AND LIME explanations side by side.
- G4. Interactive controls: a confidence-threshold slider and a heatmap-opacity
  slider update the view live.
- G5. Every scan (image, patient, prediction, confidence, timestamp) is saved.
- G6. A patient's past scans can be viewed as a history.
- G7. A scan result can be exported as a PDF report.
- G8. The tool's role (decision-support, not diagnosis) is always clear.

## 4. Non-goals (v2)
- No multi-tenant hospital system, billing, or roles beyond a basic clinician
  login.
- No real patient-identifying data from real patients during development — use
  fake/sample patient names and the project's own sample X-rays.
- No diagnosis or treatment recommendation.
- Not training/retraining the model (that is a separate data-science track).

## 5. Users
- Primary: a clinician who logs in, screens X-rays, and reviews history.
- Secondary: the project panel seeing a live, functional demo.

## 6. Core flows
A. **Auth:** register / log in -> land on a dashboard.
B. **New scan:** pick or add a patient -> upload X-ray -> Analyze ->
   see prediction + confidence + Grad-CAM + LIME + sliders -> save (auto).
C. **History:** open a patient -> see their past scans and results.
D. **Export:** from a scan, download a PDF report.

## 7. Functional requirements
- FR1. Auth: register, log in, log out. Passwords hashed, never stored plain.
- FR2. Patient CRUD: create a patient (name + minimal metadata), list patients.
- FR3. Upload X-ray (JPG/PNG), validate type, preview.
- FR4. Preprocess to model spec (224x224, /255) — see MODEL_INTERFACE.md.
- FR5. Predict class + confidence.
- FR6. Grad-CAM heatmap overlay.
- FR7. LIME explanation image (superpixels) shown next to Grad-CAM.
- FR8. Confidence-threshold slider: changes the NORMAL/PNEUMONIA cutoff live and
  updates the displayed label. Heatmap-opacity slider: blends the heatmap over
  the X-ray live.
- FR9. Persist each scan: image (stored on disk or as a blob), patient id,
  predicted label, confidence, threshold used, timestamp, user id.
- FR10. Patient history view listing past scans with their results.
- FR11. Export a scan as a PDF (prediction, confidence, patient, heatmap, date,
  disclaimer).
- FR12. Persistent medical disclaimer on every screen.
- FR13. Graceful error handling throughout; never crash on bad input.

## 8. Non-functional
- NFR1. A prediction (incl. Grad-CAM) returns within a few seconds. (LIME is
  slower; show a spinner and run it on request, not automatically, if needed.)
- NFR2. Runs locally with one documented command; deployable later.
- NFR3. No secrets hard-coded; use environment variables / a config file the
  user fills in.
- NFR4. Readable, commented code; decisions explained.

## 9. Success criteria
- Log in -> upload for a patient -> get prediction + Grad-CAM + LIME + working
  sliders -> it's saved -> view it later in history -> export a PDF.
- Swapping mock <-> real model is a one-line change.
- No patient data leaves the app; disclaimer always visible.

## 10. Known performance note for the agent
LIME is computationally heavier than Grad-CAM (it perturbs the image many times).
Design for this: run LIME on a button/toggle with a spinner, cache results per
scan, and keep the number of samples modest so the demo stays responsive.
