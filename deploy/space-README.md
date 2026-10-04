---
title: Pneumonia Screening API
emoji: 🫁
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Backend API for a chest X-ray screening decision-support tool
---

# Pneumonia Screening API

Backend (FastAPI + TensorFlow) for a clinical **decision-support** tool — **not a
diagnosis**. The user interface is a separate Next.js app; this Space only serves
`/api/*`, and every data endpoint requires a logged-in clinician.

The trained model is downloaded at startup from a private model repo; no model
weights or secrets are stored in this Space.
