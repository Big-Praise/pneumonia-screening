# Pneumonia Screening — clinical decision-support (v2)

A local web app around a trained chest X-ray classifier (MobileNetV2). A clinician
logs in, adds a patient, uploads an X-ray and gets a **screening result** with its
confidence, a **Grad-CAM** heatmap and a **LIME** explanation. Two sliders let them
adjust the **confidence threshold** and **heatmap opacity**. Every scan is saved,
viewable in **patient history** and exportable as a **PDF report**.

> **Decision-support only — not a diagnosis.** The model can miss pneumonia and can
> over-flag normal X-rays. A qualified clinician makes the final decision. This
> notice is shown on every screen and on every page of every report.

---

## 1. Requirements

| | |
|---|---|
| Python | **3.10 – 3.13** (TensorFlow has no build for 3.14 yet) |
| Disk | ~2 GB for the virtual environment (TensorFlow is most of it) |
| OS | Windows, macOS or Linux |
| Model file | `pneumonia_model.keras` (or `.h5`) — supplied separately, not in git |

## 2. Setup

From this folder (`pneumonia-v2/`):

**Windows (PowerShell)**
```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

**macOS / Linux**
```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

TensorFlow and Keras are pinned to **2.20.0 / 3.13.2**, the versions the model was
trained and saved with in Colab. Don't change them without re-checking that the
model loads (section 8).

### Slow or unstable internet?
TensorFlow is a single ~330 MB download, and pip restarts it from zero when the
connection drops. Download it separately with a resumable tool first, then install
from the file:

Windows, Python 3.13. For other platforms or versions, pick the matching file at
pypi.org/project/tensorflow/2.20.0/#files. Use `curl.exe`, not `curl`, because in
PowerShell `curl` is a different command:
```powershell
curl.exe -L -C - --retry 50 -o tensorflow-2.20.0-cp313-cp313-win_amd64.whl https://files.pythonhosted.org/packages/9b/9e/02e201033f8d6bd5f79240b7262337de44c51a6cfd85c23a86c103c7684d/tensorflow-2.20.0-cp313-cp313-win_amd64.whl
.venv\Scripts\python -m pip install tensorflow-2.20.0-cp313-cp313-win_amd64.whl
.venv\Scripts\python -m pip install -r requirements.txt --resume-retries 20
```
If the download stops, run the same `curl.exe` line again; `-C -` continues where
it left off.

## 3. Add the model

Copy the trained model into this folder:
```
pneumonia-v2/
├── app.py
└── pneumonia_model.keras   ← here
```
That's the only connection step. On startup the app looks for
`pneumonia_model.keras`, then `pneumonia_model.h5`.

- **File present:** the real model is used, and the sidebar shows its name.
- **File absent:** a mock predictor is used, and every screen shows a **DEMO MODE**
  banner. Demo results and heatmaps are meaningless and are labelled that way.
- **File present but broken:** the app shows the load error and refuses to analyse.
  It never quietly falls back to fake results.

## 4. Run

```bash
.venv/Scripts/python -m streamlit run app.py      # Windows
.venv/bin/python -m streamlit run app.py          # macOS / Linux
```
Then open **http://localhost:8501**. The first page load takes a few seconds while
TensorFlow starts.

### First use
1. **Register** a clinician account. Use a made-up name during development.
2. **Patients → Add a patient**, or add one from **New Scan**.
3. **New Scan**: pick the patient, upload a JPG/PNG (try `sample_xrays/`), then click **Analyze**.
   The result is saved straight away at threshold 0.50.
4. On the result screen:
   - **Confidence threshold** slider: the label updates live. Click **Save threshold**
     to record a new value with the scan.
   - **Heatmap opacity** slider: fade Grad-CAM in and out.
   - **Show LIME explanation**: about a minute the first time, then saved for that scan.
   - **Download PDF report**: uses the *saved* record.
5. **Patients → (select a patient)** shows their history. Click **Open** to reopen any scan.

> **Before a live demo:** open each demo scan and run LIME once beforehand. After
> that it loads instantly.

## 5. Configuration — what Praise sets

Everything is read from environment variables in [config.py](config.py). There are
no secrets in the code. Copy [.env.example](.env.example) as a reference. Search
the code for `TODO (Praise)` to find every place a deployment decision is needed.

| Variable | Default | Purpose |
|---|---|---|
| `REGISTRATION_CODE` | *(empty = open)* | Invite code needed to create an account. **Set this before anyone else can reach the app.** |
| `DATABASE_URL` | `sqlite:///app.db` | Any SQLAlchemy URL. For Postgres: `postgresql+psycopg://user:pass@host/db` (also `pip install "psycopg[binary]"`). |
| `UPLOAD_DIR` | `./uploads` | Where X-ray images and saved LIME results live. Put it on persistent, backed-up storage. |

Set one in PowerShell for the current session with `$env:REGISTRATION_CODE = "..."`,
or with `export REGISTRATION_CODE=...` on macOS/Linux.

**There is no session secret to configure.** Login state is held server-side per
browser tab (Streamlit session state), and passwords are stored as bcrypt hashes
with a per-password salt.

### Deployment checklist (TODO Praise)
- [ ] Set `REGISTRATION_CODE`.
- [ ] Serve over **HTTPS** behind a reverse proxy. Then change `server.address` in
      [.streamlit/config.toml](.streamlit/config.toml); it is `localhost` now, so
      only this machine can reach the app.
- [ ] Add **per-IP rate limiting** on login in the proxy or host. The app only slows
      repeated failures within one browser session.
- [ ] Set `client.showErrorDetails = "none"` in `.streamlit/config.toml`.
- [ ] Move to Postgres if more than one machine or user will use it at once.
- [ ] Back up the database **and** `UPLOAD_DIR` together. Scans reference image files.
- [ ] Confirm data handling meets your institution's rules before using any real
      patient data. Development uses fake names and the sample X-rays only.

## 6. Tests

```bash
.venv/Scripts/python -m pytest -q tests
```
There are 37 tests covering the following:
- **Auth:** bcrypt hashing, never plaintext; login; validation; registration code.
- **Per-user data scoping:** one clinician can't read, change or attach scans to
  another's patients.
- **Preprocessing:** 224×224, values /255.
- **Threshold logic.**
- **Upload validation:** junk, truncated, tiny and path-traversal inputs.
- **Grad-CAM shape and overlay.**
- **LIME:** the prediction wrapper returns two columns that sum to 1, masks, and caching.
- **PDF content:** includes the disclaimer, contains none of the forbidden words,
  and has no patient name in the filename.

The tests use a throwaway database and the untrained demo network, so they don't
need the model file and never touch `app.db`.

## 7. Project layout

```
app.py             Streamlit UI: login, dashboard, new scan, result view, history
auth.py            register / login, bcrypt hashing
db.py              SQLAlchemy models (User, Patient, Scan) + per-user queries
config.py          all settings from environment variables
model_loader.py    loads the .keras model (cached), or the mock if absent
mock_predictor.py  DEMO-mode stand-in (fake probabilities + untrained net for explainers)
predict.py         preprocess (224x224, /255) -> probability -> label/confidence
gradcam.py         Grad-CAM for the nested MobileNetV2 + overlay
lime_explain.py    LIME (superpixels) + on-disk cache + Grad-CAM agreement
report.py          PDF report (reportlab)
storage.py         upload validation, safe image storage
tests/             pytest suite
sample_xrays/      6 sample images (3 normal, 3 pneumonia) from the project dataset
docs/              PRD, guardrails, data model, specs
uploads/           runtime: saved images + lime/ cache   (git-ignored)
app.db             runtime: SQLite database              (git-ignored)
```

## 8. How it works

- **Prediction:** the image is converted to RGB, resized to 224×224 and scaled by
  1/255, matching training. The sigmoid output is *p* = probability of pneumonia.
  The label is PNEUMONIA if *p* ≥ threshold. Confidence is *p* for PNEUMONIA and
  1 − *p* for NORMAL. The raw *p* is saved with every scan, so a scan can be
  re-thresholded later and stay reproducible.
- **Grad-CAM:** a manual forward pass through the nested MobileNetV2 base inside a
  gradient tape. This avoids the graph and duplicate-name errors of reaching into
  nested models. It uses the last convolutional layer (7×7×1280). The target is the
  final layer's *pre-sigmoid* score, because the model is often extremely confident
  (*p* ≈ 0 or 1), where probability gradients vanish and the map goes blank.
- **LIME:** about 50 SLIC superpixels and 1,000 perturbed copies. "Removed"
  superpixels become their own mean brightness, not black, because black looks like
  air on an X-ray and biases the result. Both classes are explained in one run, so
  flipping the threshold never re-runs LIME.
- **Check the model loads** after changing any package version:
  ```bash
  .venv/Scripts/python -c "import model_loader; p=model_loader.load_predictor(); print(p.source)"
  ```

## 9. Findings worth discussing (from building the explainers)

On the six sample X-rays:
- **The model is right on all six.** The probabilities for the normal samples were
  0.001–0.011, and for the pneumonia samples 0.77–1.00.
- **Grad-CAM often highlights regions outside the lungs:** image edges, diaphragm,
  upper abdomen.
- **LIME's evidence for the pneumonia cases is weak.** Hiding any single region barely
  moves the prediction.
- **Grad-CAM and LIME agree only 0–26% of the time.**

Together these suggest the model may partly rely on non-clinical cues. Shortcut
learning like this is a known risk with this pediatric, single-source dataset. The
app surfaces this rather than hiding it, which is the point of showing two
explanations side by side.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `No matching distribution found for tensorflow==2.20.0` | You're on Python 3.14. Create the venv with 3.10–3.13 (`py -3.13 -m venv .venv`). |
| Install keeps failing partway | See *Slow or unstable internet* in section 2. |
| Sidebar says **Model: failed to load** | The error is shown on New Scan. Check the file isn't truncated and that the TF/Keras versions match. |
| DEMO MODE banner but you added the model | The file must be named exactly `pneumonia_model.keras` (or `.h5`) and be in this folder. Restart the app. |
| LIME takes minutes | Expected on CPU (~1 min per scan). It runs once per scan, then loads from `uploads/lime/`. |
| `Port 8501 is already in use` | Another copy is running. Close it, or add `--server.port 8502`. |

## 11. New web app (Next.js + FastAPI) and going live

v2.1 adds a custom web interface (`web/`, Next.js) backed by a FastAPI API (`api/`).
The API reuses the same Python modules as the Streamlit app.

**Live site:** https://pneumonia-screening.vercel.app (Vercel, free Hobby plan).
The website only works while the backend is running on this PC (tunnel mode, below).

### Tunnel mode ($0): the backend runs on this PC
```
Browser -> Vercel (website) -> Cloudflare quick tunnel -> this PC: FastAPI + model + app.db
```
Patient data and X-rays never leave this machine. To start (and update the site):
```powershell
cd C:\Users\USER\Downloads\pneumonia-v2-foundation\pneumonia-v2
.venv\Scripts\python serve_public.py --deploy
```
- Keep that window open while the site is in use. Ctrl+C stops it.
- Quick-tunnel URLs change on every start. `--deploy` rebuilds the Vercel site with
  the new URL (about 1 minute). It needs `vercel login` done once.
- The first run creates `.env.backend` (git-ignored), which holds a random session
  key and the **registration code**. Open the file to read the code. People need it
  to create an account. Change it there and restart to rotate it.
- `cloudflared` lives in `tools/` (git-ignored). Download `cloudflared-windows-amd64.exe`
  from Cloudflare's GitHub releases and save it as `tools/cloudflared.exe`.

### Local development
```powershell
# terminal 1 (API, http://127.0.0.1:8000)
$env:COOKIE_SECURE="0"; .venv\Scripts\python -m uvicorn api.main:app --port 8000
# terminal 2 (web, http://localhost:3000)
cd web; npm install; npm run dev
```

### Later: always-on hosting (when a card is available)
The backend is ready for **Google Cloud Run**: `Dockerfile` + `.dockerignore`, request-based
billing, max instances 1, 2 GiB / 2 vCPU. Deploy it from GitHub in the Cloud Console, with
env vars `DATABASE_URL` (Neon, pooled), `JWT_SECRET`, `REGISTRATION_CODE`, `HF_TOKEN`
(read) and `MODEL_HF_REPO=ZPraise/pneumonia-model` (the private model repo). Then redeploy
Vercel with `BACKEND_URL=<Cloud Run URL>`:
`cd web; vercel deploy --prod --build-env BACKEND_URL=<url> --env BACKEND_URL=<url>`.

### Current setup: ngrok permanent URL (preferred over the quick tunnel)
- Backend URL: `https://rearview-uncork-clothes.ngrok-free.dev` (free ngrok static domain).
  It's set once as `BACKEND_URL` in Vercel → Settings → Environment Variables.
- `.env.backend` has `NGROK_DOMAIN=...`, so `serve_public.py` uses ngrok automatically.
  **No redeploy is needed on restart.** Just run `.venv\Scripts\python serve_public.py`.
- `tools/ngrok.exe` comes from ngrok's official download. Run
  `tools\ngrok.exe config add-authtoken <token>` once per PC.
- Vercel deploys automatically on every push to `main` (Root Directory = `web`).
- `web/src/proxy.ts` adds `ngrok-skip-browser-warning` to every `/api` request, so
  ngrok's free-tier warning page never breaks the app.
- Free plan limits: about 1 GB/month of traffic, and only one ngrok agent online at a time.
- Force the old Cloudflare quick tunnel with `serve_public.py --cloudflare --deploy`.
