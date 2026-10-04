"""Pneumonia Screening — Streamlit entry point.

Decision: all UI lives here (per CLAUDE.md); data/auth/ML live in their own
modules so they stay testable without Streamlit. Routing is a simple
session_state key rather than Streamlit multipage, so the login gate and the
always-on disclaimer are enforced in exactly one place (main()).
"""
import logging
import time
from datetime import datetime
from functools import partial
from html import escape

import numpy as np
import streamlit as st
from PIL import Image

import auth
import config
import db
import gradcam
import lime_explain
import model_loader
import predict
import report
import storage

st.set_page_config(
    page_title="Pneumonia Screening",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="auto",
)

DISCLAIMER = (
    "Decision-support only — not a diagnosis. This tool gives a screening "
    "result from a machine-learning model. It can miss cases and over-flag "
    "normal X-rays. A qualified clinician must make the final decision."
)

LIMITATIONS = (
    "- The model can **miss pneumonia** and can **over-flag normal** X-rays.\n"
    "- Training data was likely **pediatric and single-source**; performance on "
    "other populations or scanners is unknown.\n"
    "- Sliders change how a result is **displayed**, not the model itself."
)

CSS = """
<style>
  .block-container { padding-top: 1.5rem; max-width: 1200px; }
  .banner { padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.92rem; margin-bottom: 0.8rem; }
  .disclaimer { background: #fff8e6; border: 1px solid #f0d9a0; border-left: 4px solid #d99a1e; color: #4a3a12; }
  .demo { background: #eef2ff; border: 1px solid #c7d2fe; border-left: 4px solid #4f46e5; color: #1e1b4b; }
  .brand { font-size: 1.6rem; font-weight: 700; color: #0f766e; margin-bottom: 0; }
  .brand-sub { color: #4b6460; margin-top: 0.1rem; }
  .who { color: #4b6460; font-size: 0.9rem; margin-top: -0.4rem; }
  .result { border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.8rem; }
  .result.normal { background: #e6f4f1; border: 1px solid #99d1c6; }
  .result.pneumonia { background: #fff4e0; border: 1px solid #f2c27a; }
  .result .kicker { font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; color: #4b6460; }
  .result .headline { font-size: 1.7rem; font-weight: 700; margin: 0.1rem 0; }
  .result.normal .headline { color: #0f766e; }
  .result.pneumonia .headline { color: #b45309; }
  .result .sub { color: #33504b; }
</style>
"""

log = logging.getLogger("screening")

PAGES = ["Dashboard", "New Scan", "Patients"]
SEX_OPTIONS = ["", "Female", "Male", "Other"]
DISPLAY_MAX_PX = 640


# ------------------------------------------------------------------ resources

@st.cache_resource
def _init_database() -> bool:
    """Create tables once per server process, not on every rerun."""
    db.init_db()
    return True


@st.cache_resource(show_spinner="Loading the screening model…")
def get_predictor():
    """Load once per server process. Returns (predictor, error_message)."""
    try:
        return model_loader.load_predictor(), None
    except model_loader.ModelLoadError as e:
        return None, str(e)


# ------------------------------------------------------------------- helpers

def banner(kind: str, html_text: str) -> None:
    st.markdown(f'<div class="banner {kind}">{html_text}</div>', unsafe_allow_html=True)


def render_disclaimer() -> None:
    """Shown at the top of every screen (GUARDRAILS: always visible)."""
    banner("disclaimer", f"⚕️ {DISCLAIMER}")


def current_user() -> auth.AuthUser | None:
    return st.session_state.get("user")


def go(page: str) -> None:
    """Button callback: callbacks run before widgets, so the nav radio can be set."""
    st.session_state.page = page


def fmt_dt(dt) -> str:
    return db.as_utc(dt).astimezone().strftime("%d %b %Y, %H:%M")


# ----------------------------------------------------------------- auth screens

def login_screen() -> None:
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown('<p class="brand">🫁 Pneumonia Screening</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="brand-sub">Chest X-ray decision-support for clinicians</p>',
            unsafe_allow_html=True,
        )
        tab_login, tab_register = st.tabs(["Log in", "Register"])

        with tab_login:
            with st.form("login", clear_on_submit=False):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", type="primary",
                                                  width="stretch")
            if submitted:
                # Slow repeated failures in this browser session. Real brute-force
                # protection belongs at the hosting layer (per-IP rate limiting).
                # TODO (Praise): add rate limiting in your reverse proxy/host when deploying.
                fails = st.session_state.get("login_failures", 0)
                if fails >= 3:
                    time.sleep(min(2 ** (fails - 3), 8))
                user = auth.authenticate(username, password)
                if user is None:
                    st.session_state.login_failures = fails + 1
                    # Same message for unknown user and wrong password.
                    st.error("Incorrect username or password.")
                else:
                    st.session_state.user = user
                    st.session_state.page = "Dashboard"
                    st.rerun()

        with tab_register:
            with st.form("register", clear_on_submit=False):
                full_name = st.text_input("Full name (optional)")
                new_username = st.text_input("Username", help="3–32 characters: letters, numbers, . _ -")
                new_password = st.text_input("Password", type="password",
                                             help=f"At least {auth.MIN_PASSWORD_LEN} characters.")
                confirm = st.text_input("Confirm password", type="password")
                code = ""
                if auth.registration_requires_code():
                    code = st.text_input("Registration code", type="password",
                                         help="Ask your administrator for the code.")
                created = st.form_submit_button("Create account", width="stretch")
            if created:
                if new_password != confirm:
                    st.error("Passwords do not match.")
                else:
                    try:
                        user = auth.register_user(new_username, new_password, full_name, code)
                    except auth.AuthError as e:
                        st.error(str(e))
                    else:
                        st.session_state.user = user
                        st.session_state.page = "Dashboard"
                        st.rerun()
            if not auth.registration_requires_code():
                st.caption("Development mode: registration is open (no REGISTRATION_CODE set).")


def logout() -> None:
    # Clear everything tied to this browser session, not just the user key.
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# ------------------------------------------------------------- logged-in shell

def sidebar(user: auth.AuthUser, predictor, model_error) -> str:
    with st.sidebar:
        st.markdown('<p class="brand">🫁 Screening</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="who">Signed in as <b>{escape(user.display_name)}</b></p>',
                    unsafe_allow_html=True)
        page = st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")
        st.divider()
        if model_error:
            st.caption("Model: ❌ failed to load")
        elif predictor.is_demo:
            st.caption("Model: DEMO (mock predictor)")
        else:
            st.caption(f"Model: {predictor.source}")
        with st.expander("Known limitations"):
            st.markdown(LIMITATIONS)
        if st.button("Log out", width="stretch"):
            logout()
    return page


def render_result(scan: db.Scan, patient: db.Patient, label: str, confidence: float) -> None:
    """The screening result card, for the label at the CURRENTLY displayed threshold."""
    is_pn = label == predict.PNEUMONIA
    css = "pneumonia" if is_pn else "normal"
    headline = "Findings suggest pneumonia" if is_pn else "No pneumonia pattern detected"
    sub = (f"Screening result: likely <b>{label}</b> · "
           f"{escape(patient.name)} · {fmt_dt(scan.created_at)}")
    st.markdown(
        f'<div class="result {css}"><div class="kicker">Screening result</div>'
        f'<div class="headline">{headline}</div><div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )
    st.progress(confidence, text=f"Confidence in this result: {confidence:.0%}")
    if confidence < 0.5:
        # Threshold moved past p: the label comes from the cutoff, not the model's lean.
        st.warning("The model itself leans the other way here; this label comes from "
                   "the threshold setting. Treat it as borderline.")


def _save_threshold(user_id: int, scan_id: int) -> None:
    """Button callback (runs before the rerun, so the page reflects the save)."""
    thr = st.session_state[f"thr_{scan_id}"]
    db.update_scan_threshold(user_id, scan_id, thr)
    st.toast(f"Saved threshold {thr:.2f} with this scan.")


def render_threshold_control(scan: db.Scan, threshold: float) -> None:
    st.slider(
        "Confidence threshold", 0.0, 1.0, float(scan.threshold_used), 0.01,
        key=f"thr_{scan.id}",
        help="PNEUMONIA is shown when the model's probability p ≥ this threshold.",
    )
    st.caption(
        "Lowering the threshold catches more pneumonia but raises more false alarms; "
        "raising it is stricter but misses more cases. This changes how the result is "
        "**displayed** — it does not change the model or its probability."
    )
    st.caption(f"Model pneumonia probability p = {scan.pneumonia_prob:.3f} · "
               f"saved threshold = {scan.threshold_used:.2f}")
    if abs(threshold - scan.threshold_used) > 1e-9:
        c_note, c_btn = st.columns([2, 1])
        c_note.info(f"Showing threshold {threshold:.2f} — not saved "
                    f"(saved: {scan.threshold_used:.2f}).")
        c_btn.button("Save threshold", key=f"save_thr_{scan.id}", width="stretch",
                     on_click=_save_threshold, args=(scan.user_id, scan.id))
    else:
        st.caption("✓ Result saved at this threshold.")


def display_size(img: Image.Image) -> Image.Image:
    """Downscale for screen so overlays re-blend instantly when sliders move."""
    img = img.copy()
    img.thumbnail((DISPLAY_MAX_PX, DISPLAY_MAX_PX))
    return img


@st.cache_data(max_entries=64, show_spinner=False)
def cached_heatmap(image_rel: str, target_label: str) -> np.ndarray:
    """Grad-CAM per (stored image, label). Stored images never change, so the
    path is a safe cache key; switching scans or labels recomputes once."""
    predictor, _ = get_predictor()
    x = predict.preprocess(storage.open_image(image_rel))
    return gradcam.compute_heatmap(predictor.keras_model, x, target_label)


def render_scan_view(scan: db.Scan, patient: db.Patient, predictor) -> None:
    """Full result screen for one saved scan: result card + explanations.
    Used right after analysis and (M6) when reopening from history."""
    # The slider is drawn below the card but read here first via session_state,
    # so moving it updates the label, confidence and Grad-CAM target in one rerun.
    threshold = st.session_state.get(f"thr_{scan.id}", scan.threshold_used)
    label, confidence = predict.classify(scan.pneumonia_prob, threshold)

    c_card, c_thr = st.columns([1.3, 1], gap="large")
    with c_card:
        render_result(scan, patient, label, confidence)
        render_pdf_download(scan, patient, threshold)
    with c_thr:
        render_threshold_control(scan, threshold)

    st.subheader("What drove this result")
    st.caption("Two independent explanations; agreement increases confidence in the "
               "highlighted region.")
    try:
        original = display_size(storage.open_image(scan.image_path))
    except storage.ImageError as e:  # e.g. file removed from uploads/ by hand
        st.error(f"{e} The saved result above is still valid; explanations need the image.")
        return
    if predictor is None:  # model failed to load — saved data is shown, nothing recomputed
        st.image(original, caption="Original X-ray", width=360)
        st.warning("The model is not loaded, so explanations can't be computed right now.")
        return
    demo = " — DEMO: meaningless" if predictor.is_demo else ""
    heatmap = None
    c_orig, c_cam, c_lime = st.columns(3, gap="medium")
    with c_orig:
        st.image(original, caption="Original X-ray", width="stretch")
    with c_cam:
        try:
            with st.spinner("Computing Grad-CAM…"):
                heatmap = cached_heatmap(scan.image_path, label)
        except Exception:  # noqa: BLE001 — show an honest error, never a fake map
            st.error("Grad-CAM could not be computed for this image.")
        else:
            opacity = st.session_state.get(f"opacity_{scan.id}", config.DEFAULT_OPACITY)
            st.image(gradcam.overlay(original, heatmap, opacity),
                     caption=f"Grad-CAM for “{label}”{demo}", width="stretch")
            if heatmap.max() == 0:
                st.warning("Grad-CAM found no region pushing towards this result.")
        # Rendered below the image but read above via session_state, so a slider
        # move re-blends the cached heatmap without recomputing Grad-CAM.
        st.slider("Heatmap opacity", 0.0, 1.0, config.DEFAULT_OPACITY, 0.05,
                  key=f"opacity_{scan.id}",
                  help="Fade the heatmap to see the anatomy underneath. Display only.")
    with c_lime:
        render_lime(scan, label, original, heatmap, predictor, demo)
    st.caption(
        "**Grad-CAM** (left): red = regions that most pushed the model towards this "
        "result; computed on a coarse 7×7 grid, so broad regions, not lesion boundaries. "
        "**LIME** (right): green = the superpixels whose removal most weakened this "
        "result. Highlights outside the lungs suggest the model may be using "
        "non-clinical cues — interpret with care."
    )


@st.cache_data(max_entries=32, show_spinner=False)
def cached_pdf(scan_id: int, image_rel: str, label: str, confidence: float, prob: float,
               threshold: float, created_iso: str, patient: tuple, clinician: str,
               lime_saved: bool) -> bytes:
    """PDF for the SAVED record. Every input that changes the report is an argument,
    so re-saving a threshold or running LIME produces a fresh PDF automatically."""
    predictor, _ = get_predictor()
    original = display_size(storage.open_image(image_rel))
    try:
        heatmap = cached_heatmap(image_rel, label)
        cam = gradcam.overlay(original, heatmap, 0.45)
    except Exception:  # noqa: BLE001 — report says "unavailable" rather than faking it
        cam, heatmap = None, None
    lime_img, weak, agree = None, False, None
    lime_res = lime_explain.load_cached(image_rel) if lime_saved else None
    if lime_res is not None:
        mask = lime_explain.mask_for(lime_res, label)
        lime_img = lime_explain.overlay(original, mask)
        weak = lime_explain.top_weight(lime_res, label) < lime_explain.WEAK_WEIGHT
        agree = lime_explain.agreement(heatmap, mask) if heatmap is not None else None
    name, age, sex = patient
    return report.build_pdf(report.ReportData(
        scan_id=scan_id, scan_time=datetime.fromisoformat(created_iso),
        patient_name=name, patient_age=age, patient_sex=sex, clinician=clinician,
        label=label, confidence=confidence, pneumonia_prob=prob, threshold=threshold,
        model_source=predictor.source if predictor else "model not loaded",
        is_demo=bool(predictor and predictor.is_demo),
        original=original, gradcam=cam, lime=lime_img, lime_weak=weak, agreement=agree,
    ))


def render_pdf_download(scan: db.Scan, patient: db.Patient, threshold: float) -> None:
    created = db.as_utc(scan.created_at).astimezone()
    try:
        with st.spinner("Preparing PDF…"):
            pdf = cached_pdf(
                scan.id, scan.image_path, scan.predicted_label, scan.confidence,
                scan.pneumonia_prob, scan.threshold_used, created.isoformat(),
                (patient.name, patient.age, patient.sex), current_user().display_name,
                lime_explain.load_cached(scan.image_path) is not None,
            )
    except Exception:  # noqa: BLE001
        st.error("The PDF report could not be generated.")
        return
    st.download_button("⬇️ Download PDF report", pdf, file_name=report.filename(scan.id, created),
                       mime="application/pdf", key=f"pdf_{scan.id}", width="stretch")
    if abs(threshold - scan.threshold_used) > 1e-9:
        st.caption(f"The PDF uses the saved threshold ({scan.threshold_used:.2f}). "
                   "Save the threshold to include the current one.")


def render_lime(scan: db.Scan, label: str, original: Image.Image, heatmap, predictor,
                demo: str) -> None:
    """LIME column: on request only (slow), then cached on disk per scan."""
    cached = lime_explain.load_cached(scan.image_path)
    show = st.toggle("Show LIME explanation", key=f"lime_{scan.id}", value=cached is not None)
    if not show:
        st.caption(f"LIME re-runs the model on {config.LIME_NUM_SAMPLES:,} altered copies "
                   "of the image — about a minute. Results are saved, so each scan "
                   "only runs once.")
        return
    if cached is None:
        with st.spinner(f"Running LIME on {config.LIME_NUM_SAMPLES:,} perturbed images "
                        "(about a minute)…"):
            try:
                img = storage.open_image(scan.image_path)
                cached = lime_explain.compute(predictor, img)
                lime_explain.save_cached(scan.image_path, cached)
            except Exception:  # noqa: BLE001 — honest error, no fabricated regions
                st.error("LIME could not be computed for this image.")
                return
    mask = lime_explain.mask_for(cached, label)
    st.image(lime_explain.overlay(original, mask), width="stretch",
             caption=f"LIME for “{label}” — top {lime_explain.TOP_FEATURES} regions{demo}")
    if not mask.any():
        st.warning("LIME found no region supporting this result.")
        return
    if lime_explain.top_weight(cached, label) < lime_explain.WEAK_WEIGHT:
        st.caption("⚠️ Weak evidence: hiding any single region barely changes the "
                   "prediction, so these highlights are only loosely supported.")
    if heatmap is not None:
        agree = lime_explain.agreement(heatmap, mask)
        if agree is not None:
            word = "high" if agree >= 0.5 else "partial" if agree >= 0.2 else "low"
            st.caption(f"Agreement with Grad-CAM: **{word}** ({agree:.0%} of LIME's "
                       "regions fall in Grad-CAM's hottest area).")


# ---------------------------------------------------------------------- pages

def dashboard(user: auth.AuthUser) -> None:
    st.title(f"Welcome, {user.display_name}")
    n_patients, n_scans = db.count_for_user(user.id)
    c1, c2, c3 = st.columns([1, 1, 1.2])
    c1.metric("Your patients", n_patients)
    c2.metric("Your screenings", n_scans)
    with c3:
        st.write("")
        st.button("➕ New scan", type="primary", on_click=go, args=("New Scan",),
                  width="stretch")

    st.subheader("Recent screenings")
    rows = db.recent_scans(user.id, limit=10)
    if not rows:
        st.caption("No screenings yet. Start with **New scan**.")
        return
    st.caption("Select a row to reopen that screening.")
    st.dataframe(
        [{
            "Date": fmt_dt(s.created_at),
            "Patient": p.name,
            "Screening result": f"likely {s.predicted_label}",
            "Confidence": f"{s.confidence:.0%}",
            "Threshold": f"{s.threshold_used:.2f}",
        } for s, p in rows],
        hide_index=True, width="stretch", key="recent_table",
        selection_mode="single-row",
        on_select=partial(_table_pick, "recent_table", [(p.id, s.id) for s, p in rows], open_scan),
    )


def patient_form(user: auth.AuthUser, key: str) -> db.Patient | None:
    """Add-patient form; returns the new patient on success."""
    with st.form(key, clear_on_submit=True):
        name = st.text_input("Name *", help="Use fake/sample names during development.")
        c1, c2 = st.columns(2)
        age = c1.number_input("Age", min_value=0, max_value=130, value=None, step=1)
        sex = c2.selectbox("Sex", SEX_OPTIONS)
        note = st.text_area("Note", height=68)
        ok = st.form_submit_button("Add patient")
    if ok:
        try:
            p = db.create_patient(user.id, name, int(age) if age is not None else None, sex, note)
        except ValueError as e:
            st.error(str(e))
            return None
        st.success(f"Added {p.name}.")
        return p
    return None


# ------------------------------------------------- patients + history (M6)
# Navigation inside the Patients page is two session keys:
#   hist_patient_id -> show that patient's history
#   open_scan_id    -> show one saved scan in the full result view
# Changes happen in button/table callbacks, which run before widgets are drawn,
# so they can also switch the sidebar page.

def open_patient(patient_id: int) -> None:
    st.session_state.hist_patient_id = patient_id
    st.session_state.pop("open_scan_id", None)
    st.session_state.page = "Patients"


def open_scan(patient_id: int, scan_id: int) -> None:
    open_patient(patient_id)
    st.session_state.open_scan_id = scan_id


def back_to_list() -> None:
    st.session_state.pop("hist_patient_id", None)
    st.session_state.pop("open_scan_id", None)


def back_to_history() -> None:
    st.session_state.pop("open_scan_id", None)


def new_scan_for(patient_id: int) -> None:
    st.session_state.scan_patient_id = patient_id
    _clear_result()
    st.session_state.page = "New Scan"


def _table_pick(table_key: str, ids: list, then) -> None:
    """Callback for a single-row selectable dataframe: act on the picked row."""
    rows = st.session_state[table_key].selection.rows
    if rows:
        then(*ids[rows[0]])


@st.cache_data(max_entries=256, show_spinner=False)
def thumbnail(image_rel: str) -> Image.Image | None:
    try:
        img = storage.open_image(image_rel)
    except storage.ImageError:
        return None
    img.thumbnail((160, 160))
    return img


def patients_page(user: auth.AuthUser, predictor) -> None:
    pid = st.session_state.get("hist_patient_id")
    if pid is not None:
        try:
            patient = db.get_patient(user.id, pid)
        except db.NotFound:
            back_to_list()
            st.rerun()
        if st.session_state.get("open_scan_id") is not None:
            saved_scan_view(user, patient, predictor)
        else:
            patient_history(user, patient)
        return

    st.title("Patients")
    with st.expander("➕ Add a patient", expanded=False):
        patient_form(user, "add_patient_page")
    rows = db.patient_summaries(user.id)
    if not rows:
        st.caption("No patients yet.")
        return
    st.caption("Select a patient to see their scan history.")
    st.dataframe(
        [{"Name": p.name, "Age": p.age, "Sex": p.sex or "", "Scans": n,
          "Last scan": fmt_dt(last) if last else "—", "Note": p.note or ""}
         for p, n, last in rows],
        hide_index=True, width="stretch", key="patient_table",
        selection_mode="single-row",
        on_select=partial(_table_pick, "patient_table", [(p.id,) for p, _, _ in rows], open_patient),
    )


def patient_history(user: auth.AuthUser, patient: db.Patient) -> None:
    st.button("← All patients", on_click=back_to_list)
    st.title(patient.name)
    facts = [f"Age {patient.age}" if patient.age is not None else None,
             patient.sex or None, f"added {fmt_dt(patient.created_at)}"]
    st.caption(" · ".join(f for f in facts if f))
    if patient.note:
        st.write(patient.note)
    st.button("➕ New scan for this patient", type="primary",
              on_click=new_scan_for, args=(patient.id,))

    scans = db.scans_for_patient(user.id, patient.id)
    st.subheader(f"Scan history ({len(scans)})")
    if not scans:
        st.caption("No scans yet for this patient.")
        return
    for scan in scans:
        with st.container(border=True):
            c_img, c_txt, c_btn = st.columns([1, 4, 1.2], vertical_alignment="center")
            thumb = thumbnail(scan.image_path)
            if thumb is not None:
                c_img.image(thumb, width=110)
            else:
                c_img.caption("image missing")
            colour = "orange" if scan.predicted_label == predict.PNEUMONIA else "green"
            c_txt.markdown(
                f"**{fmt_dt(scan.created_at)}** · :{colour}[likely {scan.predicted_label}] · "
                f"confidence {scan.confidence:.0%}"
            )
            lime_note = " · LIME saved" if lime_explain.load_cached(scan.image_path) else ""
            c_txt.caption(f"p = {scan.pneumonia_prob:.3f} · threshold {scan.threshold_used:.2f}"
                          f"{lime_note}")
            c_btn.button("Open", key=f"open_{scan.id}", width="stretch",
                         on_click=open_scan, args=(patient.id, scan.id))


def saved_scan_view(user: auth.AuthUser, patient: db.Patient, predictor) -> None:
    st.button(f"← Back to {patient.name}'s history", on_click=back_to_history)
    try:
        scan, patient = db.get_scan(user.id, st.session_state.open_scan_id)
    except db.NotFound:
        back_to_history()
        st.rerun()
    st.title("Saved screening")
    render_scan_view(scan, patient, predictor)


def _clear_result() -> None:
    st.session_state.pop("last_scan_id", None)


def new_scan_page(user: auth.AuthUser, predictor, model_error) -> None:
    st.title("New scan")

    # 1. Patient
    st.subheader("1. Patient")
    with st.expander("➕ Add a new patient"):
        new_p = patient_form(user, "add_patient_scan")
        if new_p:
            st.session_state.scan_patient_id = new_p.id
    patients = db.list_patients(user.id)
    if not patients:
        st.info("Add a patient first.")
        return
    ids = [p.id for p in patients]
    names = {p.id: f"{p.name}" + (f" ({p.age})" if p.age is not None else "") for p in patients}
    if st.session_state.get("scan_patient_id") not in ids:
        st.session_state.scan_patient_id = ids[0]
    patient_id = st.selectbox("Patient", ids, format_func=names.get,
                              key="scan_patient_id", on_change=_clear_result)

    # 2. Upload
    st.subheader("2. Chest X-ray")
    upload = st.file_uploader("Upload a chest X-ray (JPG or PNG)", type=config.ALLOWED_TYPES,
                              on_change=_clear_result)
    if upload is None:
        return
    try:
        img = storage.load_upload(upload.getvalue())
    except storage.ImageError as e:
        st.error(str(e))
        return

    if model_error:
        st.error("The screening model could not be loaded, so no result can be "
                 f"produced. Details: {model_error}")
        return

    # After analysis: the full result view replaces the preview.
    if "last_scan_id" in st.session_state:
        try:
            scan, patient = db.get_scan(user.id, st.session_state.last_scan_id)
        except db.NotFound:
            _clear_result()
            st.rerun()
        st.divider()
        render_scan_view(scan, patient, predictor)
        return

    col_img, col_act = st.columns([1, 1.2], gap="large")
    with col_img:
        st.image(display_size(img), caption="Uploaded X-ray", width="stretch")
    with col_act:
        st.write("Check this is the right patient and image, then analyze. "
                 "The result is saved automatically.")
        if st.button("Analyze", type="primary", width="stretch"):
            with st.spinner("Analyzing X-ray…"):
                try:
                    p = predict.pneumonia_probability(predictor, img)
                except Exception:  # noqa: BLE001 — never fabricate a result
                    st.error("The model could not process this image. No result was produced.")
                    return
                label, conf = predict.classify(p, config.DEFAULT_THRESHOLD)
                rel = storage.save_image(img)
                try:
                    scan = db.create_scan(user.id, patient_id, rel, label, conf, p,
                                          config.DEFAULT_THRESHOLD)
                except Exception:  # noqa: BLE001
                    storage.image_path(rel).unlink(missing_ok=True)  # no orphan files
                    st.error("Could not save the result. Please try again.")
                    return
            st.session_state.last_scan_id = scan.id
            st.rerun()  # switch to the result layout


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    _init_database()
    render_disclaimer()

    user = current_user()
    if user is None:
        login_screen()
        return

    predictor, model_error = get_predictor()
    if predictor is not None and predictor.is_demo:
        banner("demo", "🧪 <b>DEMO MODE</b> — no trained model file found. Results are "
                       "placeholders from a mock predictor and mean nothing clinically.")

    page = sidebar(user, predictor, model_error)
    try:
        if page == "Dashboard":
            dashboard(user)
        elif page == "New Scan":
            new_scan_page(user, predictor, model_error)
        elif page == "Patients":
            patients_page(user, predictor)
    except Exception:  # noqa: BLE001 — last-resort net (st.rerun/stop are BaseException, unaffected)
        # Stack trace to the server console only; never patient data, never to the screen.
        log.exception("Unhandled error on page %r", page)
        st.error("Something went wrong on this page. No result was changed. "
                 "Try again, or go back to the Dashboard.")
        st.button("Back to Dashboard", on_click=go, args=("Dashboard",))


main()
