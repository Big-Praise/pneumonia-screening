# UI / UX Spec — v2

Clean, clinical, professional. The panel specifically wants it to look like a
real tool, not an assignment. Streamlit, but tidy and intentional.

## Screens
1. **Login / Register** — simple, centered. Disclaimer visible.
2. **Dashboard** (after login) — greeting, a "New Scan" action, a patient list,
   recent scans.
3. **New Scan** — select/add patient -> upload X-ray -> preview -> Analyze.
4. **Result** — the core screen:
   - Prediction (clear, large) + confidence (number + bar).
   - Confidence-threshold slider with a one-line trade-off explanation.
   - Grad-CAM heatmap with the opacity slider.
   - A "Show LIME explanation" toggle -> LIME image beside Grad-CAM (spinner).
   - "Export PDF" button. Result auto-saved.
5. **Patient History** — a patient's past scans: thumbnail, label, confidence,
   date; click to reopen.

## Visual guidance
- Consistent, calm clinical palette (the existing teal theme is fine).
- Clear section heading on each screen; generous spacing; readable on a projector.
- Sidebar for navigation (Dashboard / New Scan / Patients / Log out) once logged
  in; show the logged-in clinician's name.
- Prediction colour: calm teal/green for NORMAL, amber accent for PNEUMONIA —
  never an alarming red that implies certainty.

## Wording
- "likely", "suggests", "screening result" — never "diagnosis" or "confirmed".
- Near the threshold slider: "Lowering the threshold catches more pneumonia but
  raises more false alarms." Near LIME/Grad-CAM: "Two independent explanations;
  agreement increases confidence in the highlighted region."

## Always
- Medical disclaimer visible on every screen.
- DEMO MODE banner when the real model is absent.
