# Data Model (Database Schema)

Three tables for v2. Keep it minimal but real. SQLAlchemy models in `db.py`.

## User (a clinician who logs in)
- id            : integer, primary key
- username      : string, unique, required
- password_hash : string, required  (bcrypt hash — NEVER store plain passwords)
- full_name     : string, optional
- created_at    : datetime, default now

## Patient (a person whose X-rays are screened)
- id            : integer, primary key
- name          : string, required        (use fake/sample names in dev)
- age           : integer, optional
- sex           : string, optional
- note          : string, optional
- created_by    : foreign key -> User.id
- created_at    : datetime, default now

## Scan (one X-ray screening event)
- id             : integer, primary key
- patient_id     : foreign key -> Patient.id
- user_id        : foreign key -> User.id   (who ran it)
- image_path     : string, required         (path under uploads/)
- predicted_label: string, required         ("NORMAL" | "PNEUMONIA")
- confidence     : float, required          (0..1)
- threshold_used : float, required          (the slider value at save time)
- created_at     : datetime, default now

## Relationships
- A User has many Patients and many Scans.
- A Patient has many Scans.
- A Scan belongs to one Patient and one User.

## Privacy rules (tie to GUARDRAILS)
- Passwords are stored ONLY as bcrypt hashes.
- During development use fake patient names and the project's own sample X-rays.
- Images are stored locally (uploads/). Nothing is sent to an external service.
- Do not log image contents or patient data to the console.

## Notes for the agent
- Store the image file on disk and keep its path in the Scan row (simplest).
  Storing the raw bytes as a blob is acceptable if the user prefers a single
  portable file — ask if unsure.
- `threshold_used` is saved because the confidence-threshold slider can change
  the label; recording the threshold makes a saved result reproducible.
- Create tables automatically on first run if they don't exist.
