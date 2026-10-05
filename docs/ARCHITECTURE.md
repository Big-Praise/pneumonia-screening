# Pneumonia Screening App: Architecture, Build History, Errors and Deployment

> **Purpose of this document.** This is a complete, factual record of how the app
> was designed, built, debugged and deployed, from the starting foundation package
> to the live site. It is written so that it can be summarised into a project report.
> Figures come from test runs and logs recorded during the build (3–5 October 2026).
> No secrets (passwords, tokens, registration codes) appear here.

---

## 1. Project summary

| Item | Detail |
|---|---|
| What it is | A full-stack **clinical decision-support** web app for chest X-ray pneumonia screening. It is **not a diagnostic tool**: a qualified clinician makes the final decision. |
| Core flow | Clinician logs in → adds a patient → uploads a chest X-ray → gets a screening result (NORMAL/PNEUMONIA + confidence) → sees **Grad-CAM** and **LIME** explanations side by side → adjusts a **confidence-threshold slider** and a **heatmap-opacity slider** → result is saved → visible in **patient history** → exportable as a **PDF report**. |
| ML model | Pre-trained transfer-learning classifier: a **MobileNetV2** base nested inside a Keras model → GlobalAveragePooling → Dense(64, ReLU) → Dropout → Dense(1, sigmoid). The team reports ~90% accuracy and ~96% pneumonia recall from training. Saved as `pneumonia_model.keras` (10.6 MB) with TensorFlow 2.20.0 / Keras 3.13.2. |
| Live site | https://pneumonia-screening.vercel.app |
| Source | Private GitHub repository `Big-Praise/pneumonia-screening` (21 commits at the time of writing). |
| Budget | **$0** hosting (requirement set during the project). |
| Size | ~2,900 lines of Python (backend, ML, data layer), ~1,450 lines of TypeScript/React (frontend), **62 automated tests**. |

Two user interfaces exist over the **same Python core**:
1. **v2 Streamlit app** (`app.py`), the first complete version (milestones M0–M8), kept as a fallback.
2. **v2.1 web app**: a custom **Next.js** frontend (`web/`) and a **FastAPI** backend (`api/`), the version that is deployed.

---

## 2. Starting point

The project began from a **foundation package**: documentation only, no code. It contained:

- `docs/PRD.md`: scope and functional requirements FR1–FR13 (auth, patient CRUD, upload, preprocessing, prediction, Grad-CAM, LIME, both sliders, persistence, history, PDF export, persistent disclaimer, graceful errors).
- `docs/GUARDRAILS.md`: non-negotiable medical-safety and privacy rules:
  - never use the words "diagnosis/diagnosed/confirmed/you have pneumonia";
  - show a disclaimer on every screen;
  - no images or patient data sent to external inference APIs;
  - bcrypt-only password storage;
  - fake patient names in development;
  - no hard-coded secrets;
  - never fabricate results when the model or an explainer fails.
- `docs/MODEL_INTERFACE.md`: the exact model contract:
  - preprocessing = RGB → **224×224** → **/255**;
  - output = sigmoid probability of PNEUMONIA (class order NORMAL=0, PNEUMONIA=1);
  - label = PNEUMONIA if p ≥ threshold;
  - confidence = p or 1−p.
- `docs/DATA_MODEL.md`: User, Patient, Scan tables.
- `docs/EXPLAINABILITY.md`: Grad-CAM (manual forward pass to avoid nested-model errors), LIME (`lime_image`), both sliders, and honesty notes.
- `docs/TECH_STACK.md`: Path A (Streamlit + SQLite + SQLAlchemy) or Path B (FastAPI + React + Postgres).
- `docs/BUILD_PLAN.md`: milestones M0–M8, each one built, run and shown before the next.
- `.claude/CLAUDE.md`: standing instructions for the AI coding agent.

**Initial decisions agreed before coding:**

| Decision | Reason |
|---|---|
| Path A (Streamlit) first | Fastest route to a complete, working app |
| Python 3.13 virtual environment | The machine's default Python 3.14 has no TensorFlow build |
| `bcrypt` used directly, not `passlib` | `passlib` is unmaintained and breaks with bcrypt ≥ 4.1 |
| Added a `Scan.pneumonia_prob` column | Label + confidence alone cannot be re-thresholded later; storing the raw probability keeps every saved result reproducible |
| Clinicians see only their own patients and scans | Data minimisation |
| Registration gated by an invite code (`REGISTRATION_CODE`) | Prevents strangers creating accounts on a public URL |
| Scan auto-saves at threshold 0.5; an explicit "Save threshold" button records changes | Resolves the conflict between "auto-save" and a live slider |
| No v1 code was available | Grad-CAM was written fresh, following the documented approach |
| Requirements pinned to TF 2.20.0 / Keras 3.13.2 | Matches the Colab training environment exactly |

---

## 3. Timeline

| Date/time | Milestone | What was delivered |
|---|---|---|
| 3 Oct 16:59 | **M0** Scaffold | Project layout, `config.py` (env-var settings), login screen with disclaimer, localhost-only server |
| 3 Oct 17:55 | **M1** Auth + DB | SQLAlchemy models, bcrypt register/login/logout, dashboard |
| 3 Oct 20:25 | **M2** End-to-end prediction | Patients, upload validation, real-model prediction, scans saved |
| 3 Oct 20:46 | **M3** Grad-CAM | Manual-forward-pass Grad-CAM + opacity slider |
| 3 Oct 21:15 | **M4** Threshold slider | Live re-labelling + explicit save of `threshold_used` |
| 3 Oct 22:22 | **M5** LIME | LIME beside Grad-CAM, on demand, cached per scan; 2× faster inference |
| 4 Oct 19:12 | **M6** History | Patient history, reopen saved scans |
| 4 Oct 19:44 | **M7** PDF | Per-scan PDF report |
| 4 Oct 20:19 | **M8** Polish | Error safety net, login slowdown, README; clean-install verification |
| 4 Oct 21:43 | **B1** API | FastAPI backend reusing the Python core; blob store (disk or DB) |
| 5 Oct 00:37 | **B2** New UI | Next.js frontend |
| 5 Oct 00:39–01:44 | **B3** Hosting attempts | Hugging Face Space (blocked), then Google Cloud Run (blocked) |
| 5 Oct 02:11 | Tunnel mode | Backend on local PC behind a Cloudflare quick tunnel; site live on Vercel |
| 5 Oct 02:33 | ngrok mode | Permanent tunnel URL; Vercel auto-deploys from GitHub |
| 5 Oct 03:00 | Edit/delete | Edit patients; delete patients (cascading) and scans |
| 5 Oct 03:10 | Change password | Account page; password change logs out other devices |

---

## 4. Final architecture

```
                         ┌──────────────────────────────────────────┐
  Clinician's browser ──►│ Vercel (free Hobby plan)                 │
  https://pneumonia-     │ Next.js 16 frontend (web/)               │
  screening.vercel.app   │ src/proxy.ts forwards /api/* ────────────┼──┐
                         └──────────────────────────────────────────┘  │ HTTPS
                                                                       ▼
                         ┌──────────────────────────────────────────┐
                         │ ngrok free static domain (tunnel)        │
                         │ rearview-uncork-clothes.ngrok-free.dev   │
                         └──────────────────────────────────────────┘
                                                                       │ outbound tunnel
                                                                       ▼
                         ┌──────────────────────────────────────────┐
                         │ Host PC (Windows), serve_public.py       │
                         │  FastAPI (api/) on 127.0.0.1:8000        │
                         │   ├─ auth.py      bcrypt + JWT cookie    │
                         │   ├─ db.py        SQLAlchemy → app.db    │
                         │   ├─ predict.py   TensorFlow model       │
                         │   ├─ gradcam.py   Grad-CAM               │
                         │   ├─ lime_explain LIME (background job)  │
                         │   ├─ report.py    PDF (reportlab)        │
                         │   └─ storage/blobstore  uploads/ on disk │
                         └──────────────────────────────────────────┘
```

**Key architectural decisions:**

1. **Shared Python core, thin interfaces.** All logic (model loading, preprocessing, Grad-CAM, LIME, PDF, database, auth) lives in plain modules with no UI code. Both the Streamlit app and the FastAPI API call the same functions, which is why the new UI could reuse about 70% of the code unchanged.
2. **Same-origin proxy.** The browser only talks to the Vercel site. `/api/*` is forwarded server-side to the backend (`web/src/proxy.ts`, the Next.js 16 "proxy", formerly middleware). This keeps the login cookie same-origin (`httpOnly`, `SameSite=Lax`, `Secure`), so no cross-site cookies or CORS are needed. Browsers increasingly block third-party cookies, so a cross-origin design would have broken login.
3. **Sliders computed in the browser.** The API returns the stored probability *p* and a coloured Grad-CAM image. The browser re-labels instantly as the threshold moves (`p ≥ threshold`, the same rule as the backend) and fades the heatmap with CSS opacity. Moving a slider costs no server round trip.
4. **Long-running work as background jobs.** LIME takes about 1–1.5 minutes on a CPU, longer than proxy and request timeouts. It runs in a single-worker background thread; the browser long-polls for progress (0→100%), and results are cached.
5. **Pluggable storage** (`blobstore.py`). X-ray PNGs and LIME results are stored either on disk (`uploads/`) or in a database table (`BLOB_BACKEND=db`, for hosts whose disk is wiped on restart). The current tunnel deployment uses disk on the host PC.
6. **Pluggable database.** `DATABASE_URL` defaults to local SQLite (`app.db`). Postgres URLs (e.g. Neon) are supported. Driver settings are adjusted for hosted connection poolers (prepared statements disabled).

### Technology stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.3 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS 4, Inter font; no icon library (inline SVGs, to save download size) |
| Backend API | FastAPI 0.142, Uvicorn, Pydantic validation, PyJWT, python-multipart |
| ML | TensorFlow 2.20.0, Keras 3.13.2, NumPy, Pillow, OpenCV (headless), `lime` 0.2, scikit-image (SLIC superpixels) |
| Data | SQLAlchemy 2.1; SQLite locally; Postgres-ready (psycopg 3) |
| Reports | reportlab (PDF) |
| Legacy UI | Streamlit 1.65 |
| Testing | pytest, FastAPI TestClient (httpx), pypdf (reads PDFs back) |
| Hosting | Vercel (frontend), ngrok tunnel to the host PC (backend), GitHub (source); Hugging Face Hub (private model repository, backup/Cloud Run source) |

---

## 5. Repository layout

```
app.py             Streamlit UI (v2, fallback)
api/main.py        FastAPI routes (HTTP only; delegates to the core)
api/security.py    JWT cookie sessions, current-user dependency, login throttle
api/services.py    model state, Grad-CAM cache, LIME job queue, PDF assembly
auth.py            register / login / change password, bcrypt
db.py              SQLAlchemy models + per-user, ownership-checked queries
config.py          every setting from environment variables (no secrets in code)
model_loader.py    loads the .keras model (local file or private HF repo), else mock
mock_predictor.py  DEMO-mode stand-in (labelled as meaningless)
predict.py         preprocess (224x224, /255) → probability → label/confidence
gradcam.py         Grad-CAM for the nested MobileNetV2 + overlay
lime_explain.py    LIME (SLIC superpixels) + cache + Grad-CAM agreement metric
report.py          PDF report
storage.py         upload validation and safe re-encoding
blobstore.py       disk-or-database file store
serve_public.py    one-command launcher: backend + tunnel (+ optional Vercel deploy)
Dockerfile         Cloud Run container (ready for future always-on hosting)
web/               Next.js frontend
tests/             62 pytest tests
docs/              PRD, guardrails, model interface, specs, this document
```

---

## 6. Data model

| Table | Columns | Notes |
|---|---|---|
| `users` | id, username (unique), password_hash, full_name, created_at | bcrypt hashes only (`$2b$12$…`); the hash never leaves `auth.py`/`db.py` |
| `patients` | id, name, age, sex, note, created_by → users.id, created_at | Visible only to the creating clinician |
| `scans` | id, patient_id, user_id, image_path, predicted_label, confidence, **pneumonia_prob**, threshold_used, created_at | `pneumonia_prob` added to the spec so results can be re-thresholded and reproduced |
| `blobs` | name (PK), data (binary), created_at | Only used when `BLOB_BACKEND=db` |

- **Ownership on every query.** Every query takes the logged-in user's id. A request for another clinician's record returns "not found" (indistinguishable from a missing record).
- **Cascading deletes.** Deleting a patient removes their scans in one transaction, then their stored images and LIME results.

---

## 7. ML pipeline

1. **Upload validation** (`storage.py`):
   - JPEG/PNG only, ≤ 10 MB, minimum 64 px;
   - decompression-bomb limit of 50 MP;
   - integrity check (`Image.verify`).
2. **Re-encoding.** The image is re-saved as PNG under a random UUID filename. This strips EXIF metadata (which can contain identifying information) and keeps user-supplied filenames, which may contain patient names, off the filesystem.
3. **Preprocessing.** Exactly as in training: RGB, 224×224, ÷255 (unchanged, per the guardrails).
4. **Inference.** The model is loaded once with `compile=False` (inference only) and warmed up. Batches run through a compiled `tf.function` with a free batch dimension.
5. **Classification.** `label = PNEUMONIA if p ≥ threshold else NORMAL`; confidence = p or 1−p.
6. **Saving.** p, label, confidence and threshold are stored; the image goes to the blob store.

**Class-order check on the 6 sample X-rays** (from the project's own dataset, test split):

| Sample | p(pneumonia) | Label at 0.5 |
|---|---|---|
| normal_1 | 0.001 | NORMAL ✓ |
| normal_2 | 0.002 | NORMAL ✓ |
| normal_3 | 0.011 | NORMAL ✓ |
| pneumonia_1 | 0.772 | PNEUMONIA ✓ |
| pneumonia_2 | 0.796 | PNEUMONIA ✓ |
| pneumonia_3 | 1.000 | PNEUMONIA ✓ |

This confirms the class order is not inverted. Six images is a sanity check, not an accuracy measurement.

**DEMO mode.** If no model file is found, a mock predictor (deterministic pseudo-random probability) and an untrained stand-in network are used. Every screen shows a DEMO banner, and explanations are labelled "meaningless". A model file that exists but fails to load produces an honest error. The app never silently falls back to fake results.

---

## 8. Explainability

### 8.1 Grad-CAM (`gradcam.py`)
- **Target layer.** The last convolutional output of the MobileNetV2 base (`out_relu`, a 7×7×1280 feature map).
- **Manual forward pass.** Building one model from the outer model's inputs to a layer inside the nested base causes "graph disconnected" / duplicate-layer-name errors. Instead, inside a `GradientTape` the code:
  1. runs a sub-model built entirely within the base's own graph, returning (conv activations, base output);
  2. applies the head layers one by one.
  The manual pass was verified to reproduce the model's own output exactly on all 6 samples.
- **Target score.** Gradients are taken of the final layer's **pre-sigmoid logit** (+z for PNEUMONIA, −z for NORMAL), not of the probability. The model is often extremely confident (p ≈ 0 or 1), where sigmoid gradients vanish and probability-based maps go blank. The logit is monotonic in p, so it explains the same decision.
- **Rendering.** Channel weights are the spatial mean of the gradients; the map is weighted-sum → ReLU → normalised, bilinearly upsampled, and coloured with a JET colormap.
- **Honesty note in the UI.** The map comes from a coarse 7×7 grid, so it shows broad regions, not lesion boundaries.
- **Speed.** About 0.6–1.2 s per image on the build PC.

### 8.2 LIME (`lime_explain.py`)
- `lime_image.LimeImageExplainer` with the following settings:
  - **SLIC superpixels:** about 50 segments, compactness 10. The default quickshift produced a few huge, irregular blobs on greyscale X-rays.
  - **1,000 samples.**
  - **Fixed random seed**, so results are reproducible.
- **`hide_color=None`.** A "removed" superpixel is replaced by its own mean brightness. With the default black (0), removal mimics *air* on an X-ray, injecting a fake "clear lung" signal. In testing, black-fill produced **no supporting regions at all** for one pneumonia image.
- **One run explains both classes**, so flipping the label with the threshold slider never re-runs LIME.
- **Display.** The top 5 positively weighted superpixels, tinted green-teal (distinct from Grad-CAM's colours).
- **Caching.** Results (superpixel map + per-class weights) are stored as `.npz` per scan, so they survive restarts and are reused by history and the PDF.
- **Two honesty indicators added beyond the spec:**
  - **Weak-evidence warning:** shown when the strongest region's weight is < 0.02, meaning hiding any single region barely changes the prediction.
  - **Agreement with Grad-CAM:** the share of LIME's highlighted area that falls inside the equally sized hottest Grad-CAM area, labelled high (≥ 50%), partial (≥ 20%) or low.

### 8.3 Sliders
- **Confidence threshold (0–1, default 0.5).** Re-labels live from the stored p. A trade-off note sits next to it: "lowering catches more pneumonia but raises more false alarms". A "borderline" warning appears if the threshold is moved past the model's own lean (shown confidence < 50%). "Save threshold" re-saves label, confidence and threshold, recomputed from p, so the saved row is always internally consistent.
- **Heatmap opacity (0–1, default 0.4).** Blends Grad-CAM over the X-ray.
- **Both are display-only**, and the UI states that they never change the model.

---

## 9. Backend API (FastAPI)

All data endpoints require a valid session cookie and are scoped to the logged-in clinician.

| Method & path | Purpose |
|---|---|
| GET `/api/health`, GET `/api/meta` | Public: liveness/model status; disclaimer, limitations, settings |
| POST `/api/auth/register` · `/login` · `/logout` · `/password`; GET `/api/auth/me` | Accounts and sessions |
| GET `/api/dashboard` | Counts + 10 most recent scans |
| GET/POST `/api/patients`; GET/PATCH/DELETE `/api/patients/{id}` | Patients (DELETE cascades to scans and files) |
| POST `/api/patients/{id}/scans` | Upload + predict + save |
| GET/PATCH/DELETE `/api/scans/{id}` | Scan detail; save threshold; delete |
| GET `/api/scans/{id}/image[?thumb=1]` | X-ray (JPEG, private cache) |
| GET `/api/scans/{id}/gradcam?label=` | Coloured heatmap for overlay |
| POST/GET `/api/scans/{id}/lime[?wait=20]`; GET `/lime/image?label=` | Start LIME / long-poll progress / overlay |
| GET `/api/scans/{id}/report.pdf` | PDF report of the **saved** record |

---

## 10. Frontend (Next.js)

**Pages:**

| Page | Contents |
|---|---|
| Login/Register | Split-screen brand panel |
| Dashboard | Stats + recent screenings |
| Patients | Searchable table |
| Patient history | Scan cards with thumbnails; edit; delete |
| New scan | Patient picker / inline add; drag-and-drop upload; preview |
| Result view | Result card, threshold control, Original / Grad-CAM / LIME panels, PDF download, delete |
| Account | Profile, change password |

**Design:**
- **Calm clinical palette:** teal for primary actions and NORMAL; amber for PNEUMONIA (never alarm-red, per the UI spec).
- **Layout:** a sticky amber disclaimer bar on every screen; a DEMO banner when relevant; a "model loading/failed" banner; a sidebar on desktop and a menu on mobile.

**Behaviour:**
- **Confirmation dialogs** (in-app, not browser pop-ups) before every permanent deletion.
- **Upload size:** images > 4 MB are downscaled to 2048 px in the browser before upload, with a visible notice, to stay under hosting request-body limits. The model only uses 224×224 anyway.
- **Clear offline message:** "The screening server is offline right now…" when the tunnel or host PC is down, instead of a raw 404.
- **Security headers** on every page: `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`; HSTS comes from Vercel. Pages are marked `noindex`.

---

## 11. Security and privacy

| Area | Implementation |
|---|---|
| Passwords | bcrypt with per-password salt; 8–72 bytes (bcrypt's 72-byte limit is enforced rather than silently truncated); never logged or returned |
| Login | Same error for unknown user and wrong password; constant-time dummy check prevents username discovery by timing; per-username lockout after 5 failures in 15 min (5-min lock) |
| Sessions | Signed JWT in an `httpOnly`, `Secure`, `SameSite=Lax` cookie (JavaScript cannot read it); 8-hour expiry; the user row is re-read on every request; the token carries a fingerprint of the password hash, so **changing the password logs out all other devices** |
| Registration | Requires the invite code (constant-time comparison) |
| Authorisation | Every query filtered by owner; other users' records return 404 |
| Uploads | Type/size/dimension checks, integrity verification, EXIF stripped, random filenames, path-traversal guard on reads |
| Secrets | Read only from environment variables / a git-ignored `.env.backend` (JWT secret + registration code, randomly generated, never printed); none in code or git history (checked with grep) |
| Data location | In tunnel mode, all patient data and images stay on the host PC; inference is local; no third-party AI API is used |
| Errors | Stack traces go to the server log only; users see generic messages; nothing patient-identifying is logged (ids only) |
| Medical wording | Automated tests assert the forbidden words never appear in the PDF; the UI uses "likely", "suggests", "screening result" |

---

## 12. Testing and verification

**Automated: 62 pytest tests, all passing.**

| File | Tests | Covers |
|---|---|---|
| `test_auth.py` | 8 | bcrypt storage (no plaintext), login, validation, duplicate usernames, registration code, change password |
| `test_core.py` | 12 | preprocessing shape/range, threshold logic incl. edge p = threshold, upload rejection (junk/truncated/tiny/path traversal), per-user scoping, threshold re-save, history ordering, edit/delete cascade |
| `test_gradcam.py` | 3 | heatmap shape/range, overlay at opacity 0 and 1, rejection of unsupported model layouts |
| `test_lime.py` | 5 | LIME wrapper returns (N,2) rows summing to 1, masks, cache round-trip, agreement metric |
| `test_report.py` | 3 | PDF contains key facts and disclaimer, no forbidden words, no patient name in filename |
| `test_api.py` | 12 (most run twice: disk and DB storage) | cookie flags, forged tokens, throttling, full scan flow, LIME job, PDF, scoping across users, edit/delete, password change logging out a second device, Cloud Run startup mode |

Tests use a throwaway database and the untrained demo network, so they don't need the model file and never touch real data.

**Manual and integration checks performed:**
- **End-to-end flows with the real model** at each milestone (Streamlit AppTest, then HTTP through the API, then through the Next.js proxy).
- **Clean-checkout install** following the README on a fresh clone: install OK, all tests passed, DEMO mode without the model file, real mode with it.
- **Live-site checks after each deploy:**
  - pages load and the disclaimer is present;
  - unauthenticated data requests return 401;
  - registration without the code is rejected;
  - security headers are present.
  Logged-in flows on the production site were tested by the project owner.

---

## 13. Deployment journey

The goal was a public URL at **$0**. The ML backend's requirements drove every decision: TensorFlow plus Grad-CAM needs full TensorFlow (gradients), about **2 GB of RAM**, and a long-running process.

| Step | Option | Outcome |
|---|---|---|
| 1 | **Vercel only** | ❌ Not possible for the backend. Vercel runs short-lived serverless functions (≤ 250 MB unzipped) with no persistent disk; TensorFlow alone is ~600 MB installed. Vercel *is* used for the frontend. |
| 2 | **Hugging Face Spaces (Docker)** | ❌ Blocked by **402 Payment Required**: Docker Spaces on free CPU now require a PRO subscription. The private **model repository** created on the HF Hub (`ZPraise/pneumonia-model`) is free and kept. |
| 3 | **Google Cloud Run** + Neon Postgres | ❌ Blocked: billing account verification needs a 6-digit code from a temporary card charge, and the code was not visible in the bank's (Access Bank) transaction narration. The code was fully adapted for Cloud Run and remains ready (see below). |
| 4 | **Cloudflare quick tunnel** (backend on the PC) | ✅ Worked with no account, but the URL changed on every restart, so each restart needed a Vercel rebuild (~1 min). |
| 5 | **ngrok free static domain** (backend on the PC) | ✅ **Current.** Permanent URL, so Vercel is configured once (`BACKEND_URL`). GitHub is connected to Vercel, so every push to `main` deploys automatically (~20 s builds). |

**Current operation.** On the host PC, `.venv\Scripts\python serve_public.py` starts the API, waits until the model is ready, opens the ngrok tunnel, and verifies the public health check.

**Trade-offs of tunnel mode:**
- **Availability:** the site works only while the host PC is on, awake, online and running the launcher.
- **Speed:** limited by the home internet connection.
- **Limits:** ngrok's free plan allows about 1 GB of traffic per month and one agent.
- **Privacy:** the advantage is that patient data never leaves the host machine.

**Cloud Run readiness** (for when a card can be verified):
- **Container:** a `Dockerfile` plus `.dockerignore` that builds only backend files.
- **Startup:** the model loads during startup (`MODEL_LOAD_BLOCKING=1`), because Cloud Run only allocates CPU during startup and requests.
- **LIME long-polling:** keeps a request open while LIME runs, so the background job keeps its CPU.
- **Database:** pooler-safe Postgres settings (Neon), and images stored in the database (container disk is ephemeral).
- **Model:** downloaded at startup from the private HF model repository using a read-only token.
- **Expected cost:** within the free tier apart from a few cents a month for container-image storage.

---

## 14. Errors encountered and how they were resolved

| # | Symptom / error | Root cause | Resolution |
|---|---|---|---|
| 1 | TensorFlow not installable | Machine default was Python 3.14 (no TF build) | Created a Python 3.13 virtual environment |
| 2 | (Prevented) bcrypt errors | `passlib` unmaintained; breaks with bcrypt ≥ 4.1 | Used `bcrypt` directly |
| 3 | `pip install` stalled; nothing installed after 30 min; restarts lost progress | Slow, unstable connection; pip restarts large downloads from zero | Downloaded the 332 MB TensorFlow wheel with resumable `curl -C -` and verified its SHA-256; installed the other packages separately so work continued in parallel |
| 4 | Only 1 of 3 pneumonia samples extracted | Truncated filenames collided | Renamed to `normal_1..3`, `pneumonia_1..3` |
| 5 | Streamlit reachable on the LAN and a public IP | Default server binding | Bound to `localhost` (`.streamlit/config.toml`) |
| 6 | Deprecation warnings: `use_container_width` | Streamlit 1.65 API change | Switched to `width="stretch"` |
| 7 | `UnicodeEncodeError` printing "≥" in tests | Windows console code page cp1252 | `PYTHONIOENCODING=utf-8` |
| 8 | Keras warning on load (optimizer variables mismatch) | Training-only optimizer state | `load_model(compile=False)` |
| 9 | Grad-CAM `TypeError: too many positional arguments` (demo net) | `InputLayer` appeared in the layer list and isn't callable | Skip `InputLayer`s in the manual pass |
| 10 | Grad-CAM `KeyError` building the sub-model (demo net) | A **Sequential** nested base has a different internal graph from a Functional one | Built the demo base as Functional, like MobileNetV2 |
| 11 | (Design) blank Grad-CAM at p ≈ 0/1 | Sigmoid saturation → vanishing gradients | Target the pre-sigmoid logit |
| 12 | LIME found **no supporting regions** for a pneumonia image | `hide_color=0` (black) looks like air on an X-ray | `hide_color=None` (superpixel mean) |
| 13 | LIME regions were huge blobs | Default quickshift on greyscale | SLIC superpixels (~50) |
| 14 | LIME took 85–96 s per scan | `model.predict()` overhead on CPU | Compiled `tf.function` batches of 64: 1,000 images went from 108 s to 53 s (~2×) |
| 15 | `st.dataframe(... args=...)` TypeError | Its `on_select` callback takes no args | `functools.partial` |
| 16 | Risk of locked files on Windows | `Image.open` keeps a file handle | Read, `copy()`, close |
| 17 | PDF 1.4 MB; footer cut words mid-way | Lossless PNG images; fixed-index text split | JPEG q90 (~62 KB); `textwrap` |
| 18 | Report text tests skipped | `pypdf` not installed | Added as a test-only dependency |
| 19 | (Checked) catch-all error handler could swallow Streamlit reruns | `st.rerun()` works by raising an exception | Verified those are `BaseException`, so `except Exception` is safe |
| 20 | Test assertion error: `Response` has no `ok` | httpx uses `is_success` | Fixed the test |
| 21 | `LIME_NUM_SAMPLES` setting ignored | Default argument bound at import time | Passed explicitly |
| 22 | Tests could have touched the real database | API startup called `init_db()` with the real URL | Test fixtures patch `DATABASE_URL`/`UPLOAD_DIR` too |
| 23 | React lint: setState in effect; unescaped `'` | React 19 hooks rules | Restructured (keyed remount, derived state); escaped entities |
| 24 | **HF Space creation: 402 Payment Required** | Docker Spaces need PRO | Changed host (see §13) |
| 25 | **GCP card verification code not found** | Bank narration didn't show the 6-digit code | Switched to tunnel mode |
| 26 | (Design) Cloud Run background work starves | CPU only during startup/requests | Blocking model load; LIME long-poll |
| 27 | (Design) Postgres pooler errors | Poolers break automatic prepared statements | `prepare_threshold=None` |
| 28 | Cross-site login wouldn't persist | Third-party cookie blocking | Same-origin proxy through Vercel |
| 29 | README edit failed (`unicodeescape` error) | `\U` in a Windows path inside a Python string | Appended with a shell heredoc instead (and noted the misleading commit message) |
| 30 | **Vercel build: "No Next.js version detected"** | GitHub-triggered build ran from the repo root; the app is in `web/` | Set Vercel Root Directory to `web` |
| 31 | **Login showed "Request failed (404)"** | `BACKEND_URL` pointed at ngrok but the backend was still on the Cloudflare tunnel, so ngrok returned its "endpoint offline" page | Moved the backend to ngrok; added a clear "server offline" message |
| 32 | (Prevented) ngrok "You are about to visit…" page breaking API/image calls | Free-tier browser warning | Proxy adds `ngrok-skip-browser-warning` to every `/api` request |
| 33 | Changing tunnel URL on each restart | Cloudflare quick tunnels are ephemeral | ngrok free static domain |
| 34 | Visual QA couldn't be automated | Browser-automation extension not connected | Project owner reviewed the UI; automated tests and HTTP checks covered behaviour |

---

## 15. Findings about the model (from the explainability work)

On the six sample images:

- **Predictions:** all six were correct at threshold 0.5.
- **Grad-CAM often highlights regions outside the lungs.** It points to image edges, the diaphragm and the upper abdomen. For one pneumonia image, the strongest region was at the image border, outside the body.
- **LIME evidence for the pneumonia images was weak.** Top superpixel weights were about 0.004–0.006, versus about 0.16 for a normal image. Hiding any single region barely changed the prediction.
- **Grad-CAM and LIME agreed only 0–26%** (sometimes up to ~47% for the opposite label).
- **LIME stability:** 1,000 samples were kept, because at 500 samples only 3–4 of the top-5 regions stayed the same (mask IoU 46–69%).

**Interpretation.** These results suggest the model may partly rely on **non-clinical cues** ("shortcut learning"), a known risk with the pediatric, single-source chest X-ray dataset. The app surfaces this rather than hiding it, which is the point of showing two independent explanations side by side. Possible remedies belong to the data-science track: lung segmentation/cropping before training, more diverse (adult, multi-site) data, and evaluating with explainability-based checks.

---

## 16. Performance

Measured on the host PC (8 CPU cores, no GPU).

| Operation | Time |
|---|---|
| Single prediction (warm) | ~0.07–0.1 s (first call ~3 s while the graph compiles) |
| Grad-CAM | ~0.6–1.2 s |
| LIME, 1,000 samples | ~58–90 s (with live progress); cached afterwards |
| Model load at startup | ~10–20 s |
| PDF generation | ~1.6 s, ~60–190 KB |
| Vercel build (auto-deploy) | ~20–25 s |

---

## 17. Limitations and future work

- **Availability.** Tunnel mode depends on the host PC being on and online. Next step: Cloud Run (ready), once a payment card can be verified.
- **Clinical use.** This is a prototype for demonstration and coursework. Real patient data would require a privacy/regulatory review (e.g. Nigeria's NDPR), audit logging, backups and formal validation.
- **Model.** Shortcut-learning indicators (§15); validated only on its original dataset. Training-side work is out of scope for the app.
- **Missing account features.** "Forgot password" (needs email), admin roles and audit trail.
- **Backups.** In tunnel mode, `app.db` and `uploads/` on the host PC should be backed up together.
- **Frontend tests.** Behaviour is covered by API tests and manual checks; browser end-to-end tests (e.g. Playwright) would be a good addition.

---

## 18. Glossary

- **Grad-CAM.** Gradient-weighted Class Activation Mapping: a heatmap of the image regions that most increased the model's score for a class.
- **LIME.** Local Interpretable Model-agnostic Explanations: perturbs superpixels and fits a simple model to see which regions change the prediction.
- **Superpixel.** A small group of similar neighbouring pixels.
- **Threshold.** The probability cutoff above which the result is labelled PNEUMONIA.
- **JWT.** JSON Web Token: a signed token proving who is logged in.
- **Tunnel.** A secure connection that makes a service on a local PC reachable at a public URL.
- **Same-origin proxy.** The website forwards API calls on the server side, so the browser only talks to one domain.
