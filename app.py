"""Pneumonia Screening — Streamlit entry point.

Decision: all UI lives here (per CLAUDE.md); data/auth/ML live in their own
modules so they stay testable without Streamlit. Routing is a simple
session_state key rather than Streamlit multipage, so the login gate and the
always-on disclaimer are enforced in exactly one place (main()).
"""
from html import escape

import streamlit as st

import auth
import config
import db
import model_loader
import predict
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

PAGES = ["Dashboard", "New Scan", "Patients"]
SEX_OPTIONS = ["", "Female", "Male", "Other"]


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
                user = auth.authenticate(username, password)
                if user is None:
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


def render_result(scan: db.Scan, patient: db.Patient) -> None:
    """The screening result card. Reused by history in M6."""
    is_pn = scan.predicted_label == predict.PNEUMONIA
    css = "pneumonia" if is_pn else "normal"
    headline = "Findings suggest pneumonia" if is_pn else "No pneumonia pattern detected"
    sub = (f"Screening result: likely <b>{scan.predicted_label}</b> · "
           f"{escape(patient.name)} · {fmt_dt(scan.created_at)}")
    st.markdown(
        f'<div class="result {css}"><div class="kicker">Screening result</div>'
        f'<div class="headline">{headline}</div><div class="sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )
    st.progress(scan.confidence, text=f"Confidence in this result: {scan.confidence:.0%}")
    st.caption(
        f"Model pneumonia probability p = {scan.pneumonia_prob:.3f} · "
        f"threshold used = {scan.threshold_used:.2f} (PNEUMONIA if p ≥ threshold). "
        "Result saved."
    )


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
    st.dataframe(
        [{
            "Date": fmt_dt(s.created_at),
            "Patient": p.name,
            "Screening result": f"likely {s.predicted_label}",
            "Confidence": f"{s.confidence:.0%}",
            "Threshold": f"{s.threshold_used:.2f}",
        } for s, p in rows],
        hide_index=True, width="stretch",
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


def patients_page(user: auth.AuthUser) -> None:
    st.title("Patients")
    with st.expander("➕ Add a patient", expanded=False):
        patient_form(user, "add_patient_page")
    patients = db.list_patients(user.id)
    if not patients:
        st.caption("No patients yet.")
        return
    st.dataframe(
        [{"Name": p.name, "Age": p.age, "Sex": p.sex or "", "Note": p.note or "",
          "Added": fmt_dt(p.created_at)} for p in patients],
        hide_index=True, width="stretch",
    )
    st.caption("Per-patient scan history arrives in M6.")


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

    col_img, col_res = st.columns([1, 1.2], gap="large")
    with col_img:
        st.image(img, caption="Uploaded X-ray", width="stretch")

    with col_res:
        if model_error:
            st.error("The screening model could not be loaded, so no result can be "
                     f"produced. Details: {model_error}")
            return
        if st.button("Analyze", type="primary", width="stretch",
                     disabled="last_scan_id" in st.session_state):
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
                except Exception:
                    storage.image_path(rel).unlink(missing_ok=True)  # no orphan files
                    st.error("Could not save the result. Please try again.")
                    return
            st.session_state.last_scan_id = scan.id

        if "last_scan_id" in st.session_state:
            try:
                scan, patient = db.get_scan(user.id, st.session_state.last_scan_id)
            except db.NotFound:
                _clear_result()
                return
            render_result(scan, patient)
            st.caption("Grad-CAM heatmap and sliders arrive in M3–M4.")


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
    if page == "Dashboard":
        dashboard(user)
    elif page == "New Scan":
        new_scan_page(user, predictor, model_error)
    elif page == "Patients":
        patients_page(user)


main()
