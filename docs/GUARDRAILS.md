# Guardrails — safety, medical responsibility, and data privacy (v2)

Non-negotiable. Override convenience, aesthetics, and speed.

## Core rule
Decision-support / screening tool. It does NOT diagnose. A qualified clinician
makes the final decision. Every screen must make this clear.

## Must
- Keep a plain-language medical disclaimer visible on every screen.
- Use cautious language: "likely", "suggests", "screening result". Always pair a
  prediction with its confidence.
- Clearly label DEMO MODE when the real model is not loaded.
- State the known limitations somewhere visible: the model can miss cases and
  over-flag normal ones; training data is likely pediatric/single-source; the
  sliders change interpretation, not the model.

## Must not
- Must NOT output "diagnosis", "diagnosed", "confirmed", or "you have pneumonia".
- Must NOT imply it replaces a doctor or supports self-diagnosis.
- Must NOT send images or patient data to any external service/API for inference.
- Must NOT fabricate results if the model or an explainer fails — show an honest
  error instead.

## Data privacy (NEW in v2, because we now store data)
- Store passwords ONLY as bcrypt hashes. Never log or display them.
- During development, use FAKE patient names and the project's own sample X-rays.
  Do not load real patient-identifying data.
- Keep all images and the database LOCAL. Nothing leaves the machine.
- Do not log image bytes or patient details to the console.
- No secrets, API keys, or default passwords hard-coded. Use environment
  variables / a config file the user fills in, with clear `# TODO (Praise)` marks.

## For the agent
- If a requested feature conflicts with these rules, stop and flag it.
- Auth is security-sensitive: use a vetted hashing library (passlib/bcrypt),
  never a home-rolled scheme, and leave secret/salt configuration to the user.
