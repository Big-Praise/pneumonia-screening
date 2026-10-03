# Build Plan — Full-Stack v2 (ordered milestones)

Build ONE milestone at a time. Run it, show it, wait for go-ahead. The order is
chosen so there's always a working app, and the hardest/slowest parts (LIME,
PDF) come after the core works.

### M0 — Scaffold + run
- Create the Path A layout from TECH_STACK.md and requirements.txt.
- App boots to a login screen with the medical disclaimer visible.
- Done: `streamlit run app.py` shows login + disclaimer.

### M1 — Auth + database
- Implement `db.py` (User, Patient, Scan per DATA_MODEL.md), auto-create tables.
- Implement `auth.py`: register, login, logout; bcrypt password hashing.
- After login, land on a simple dashboard.
- Done: can register, log in, log out; a user row exists in the DB.

### M2 — Patients + upload + mock prediction end-to-end
- Create/list patients (tied to the logged-in user).
- Upload an X-ray for a selected patient, preview it.
- Use `mock_predictor.py` to return a label + confidence; save a Scan row and
  the image under uploads/.
- Done: full flow works on the mock, data persists, DEMO MODE banner shows.

### M3 — Real model + Grad-CAM + opacity slider
- Implement `model_loader.py` (cached, mock fallback) and `predict.py`.
- Port Grad-CAM into `gradcam.py`; show the heatmap overlay.
- Add the heatmap-opacity slider (live blend).
- Done: real prediction + Grad-CAM, opacity slider works.

### M4 — Confidence-threshold slider
- Add the threshold slider; label updates live from the pneumonia probability.
- Save `threshold_used` on the Scan. Show the sensitivity/false-alarm trade-off
  note next to it.
- Done: moving the slider changes the displayed label; saved scans record it.

### M5 — LIME explanation
- Implement `lime_explain.py` using `lime_image`, shown beside Grad-CAM.
- Run on a toggle/button with a spinner; cache per scan; modest num_samples.
- Done: LIME highlights regions next to Grad-CAM, responsive enough to demo.

### M6 — Patient history
- A patient view listing past scans (thumbnail, label, confidence, date).
- Open a past scan to see its stored result.
- Done: history shows and reopens saved scans.

### M7 — PDF export
- `report.py` builds a PDF per scan: patient, date, prediction, confidence,
  heatmap image, and the disclaimer. Download button on the result + history.
- Done: a scan exports to a clean PDF.

### M8 — Polish + robustness + run docs
- Professional UI pass, consistent disclaimer, friendly errors everywhere.
- A README with setup/run steps and where to put secrets and the model file.
- Done: clean run from the README on a fresh checkout.

### Definition of done (v2)
Login -> add patient -> upload -> prediction + Grad-CAM + LIME + both sliders ->
auto-saved -> visible in patient history -> exportable as PDF, with the
disclaimer always visible and no secrets hard-coded.
