# START HERE — Prompt for Claude Code (Full-Stack v2)

Open this folder in Claude Code and paste the block below as your first message.

---

You are helping me upgrade my **Pneumonia Screening App** from a demo into a
full-stack clinical decision-support tool. I ship software for a living, so move
fast but build it RIGHT. Before writing code:

1. Read every file in `docs/` and `.claude/`. `docs/PRD.md` is the source of
   truth for scope; `.claude/CLAUDE.md` is your standing instructions;
   `docs/GUARDRAILS.md` is non-negotiable (this is a medical tool).
2. Read `docs/BUILD_PLAN.md` and build ONE milestone at a time. After each:
   run it, show it works, wait for my go-ahead.
3. Summarise the plan back to me before coding, and flag anything in the docs
   that's ambiguous or that you'd design differently. I want your pushback.

What's new in v2 versus the demo (all required):
- A real backend + **database** that stores patient records and uploaded X-ray
  images, with the prediction, confidence, and timestamp per scan.
- **Authentication** so a clinician logs in; records are tied to the logged-in
  user. I will handle final auth/secret configuration — scaffold it cleanly and
  leave clear TODOs where my keys/secrets go. Never hard-code secrets.
- A **patient history view**: see a patient's previous scans and results.
- Three explainability features on the result screen:
  (a) **Grad-CAM** heatmap (already have the logic — port it),
  (b) **LIME** explanation shown alongside Grad-CAM (not a replacement),
  (c) a **confidence-threshold slider** and a **heatmap-opacity slider**.
- An **exportable PDF report** per scan (prediction + confidence + heatmap).
- A cleaner, more professional **UI**.

Constraints:
- Follow `docs/TECH_STACK.md`. If you want to deviate, propose it first.
- The trained model is an external artifact (`pneumonia_model.keras`). Follow
  `docs/MODEL_INTERFACE.md` exactly. If it's absent, build against the mock
  predictor so everything runs end-to-end; swapping to the real model is a
  one-line change.
- Keep the medical disclaimer visible at all times (see GUARDRAILS).
- I handle the connecting, auth secrets, and fine-tuning — so wherever that's
  needed, scaffold it and mark a clear `# TODO (Praise): ...`.
- Comment non-obvious code and explain each architectural decision briefly.

Start by reading the docs and giving me your summary + any pushback.
