# Pneumonia Screening App — Full-Stack v2 Foundation

Foundation package for upgrading the pneumonia screening demo into a full-stack
clinical decision-support tool, built with Claude Code. Open this folder in
Claude Code and start with `START_HERE_PROMPT.md`.

## What v2 adds over the demo
- Clinician **login** (auth) and a **database** storing patients + X-ray scans
- **Grad-CAM + LIME** explanations side by side, plus a **confidence-threshold
  slider** and a **heatmap-opacity slider**
- **Patient history** and **exportable PDF reports**
- A cleaner, more professional UI

It remains decision-support, NOT diagnosis.

## How to use
1. Read `START_HERE_PROMPT.md` — the prompt to paste into Claude Code.
2. Claude Code reads `docs/` (PRD, context, data model, explainability, model
   interface, tech stack, build plan, UI/UX, guardrails, testing) and `.claude/`.
3. It builds one milestone at a time from `docs/BUILD_PLAN.md`.

## You (Praise) own
- Final auth/secret configuration and connecting (the docs leave clean
  `# TODO (Praise)` marks for this).
- Dropping in the trained model file `pneumonia_model.keras`.
- Fine-tuning and deployment.

## Folder map
```
pneumonia-v2/
├── README.md
├── START_HERE_PROMPT.md
├── docs/
│   ├── PRD.md
│   ├── TECH_STACK.md
│   ├── DATA_MODEL.md
│   ├── EXPLAINABILITY.md
│   ├── MODEL_INTERFACE.md
│   ├── BUILD_PLAN.md
│   ├── UI_UX.md
│   ├── GUARDRAILS.md
│   └── TESTING.md
└── .claude/
    ├── CLAUDE.md
    ├── skills.md
    └── tools.md
```

## Note
Add the real `pneumonia_model.keras` to the project root when ready; until then
the app runs against a mock predictor with a DEMO MODE banner.
