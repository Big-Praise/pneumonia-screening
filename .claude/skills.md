# Skills Guidance (v2)

Rules go in CLAUDE.md; repeatable workflows go in skills at
`.claude/skills/<name>/SKILL.md` (project-scoped, committed) — they load lazily
when a task matches their description.

## Official Anthropic skills worth installing
From `anthropics/skills`:
- **skill-creator** — scaffold the skills below.
- **pdf** — relevant: the app exports a PDF report (reportlab/fpdf at runtime,
  but the skill helps if generating templates/filled PDFs).
- **docx**, **pptx** — for updating the project report/slides, not the app.

## Project skills to create (via skill-creator)
1. **keras-inference** — the exact load + preprocess (224x224,/255) + predict +
   class-order contract from docs/MODEL_INTERFACE.md, plus the LIME predict
   wrapper. Trigger: "loading the model or running inference / preprocessing".
2. **gradcam-explainer** — the manual-forward-pass Grad-CAM for this nested
   transfer-learning model + overlay. Trigger: "Grad-CAM / heatmap".
3. **lime-image-explainer** — the lime_image workflow (superpixels,
   explain_instance, get_image_and_mask), with the performance pattern (toggle,
   spinner, cache, modest num_samples). Trigger: "LIME / superpixel explanation".
4. **streamlit-clinical-ui** — the UI/UX + guardrail house style (disclaimer,
   DEMO banner, cautious wording, slider trade-off notes). Trigger: "building or
   editing the Streamlit screens".
5. **sqlalchemy-data-layer** — the User/Patient/Scan models + session pattern
   from docs/DATA_MODEL.md. Trigger: "database models / persistence".

## Not a skill
- Medical guardrails and data-privacy rules are always-on (CLAUDE.md /
  GUARDRAILS.md), never a lazily-loaded skill.
