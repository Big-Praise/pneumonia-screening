"""Pneumonia Screening — Streamlit entry point.

Decision: all UI lives here (per CLAUDE.md); data/auth/ML live in their own
modules so they stay testable without Streamlit. Routing is a simple
session_state key rather than Streamlit multipage, so the login gate and the
always-on disclaimer are enforced in exactly one place (main()).
"""
import streamlit as st
from sqlalchemy import func, select

import auth
from db import Patient, Scan, get_session, init_db

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

CSS = """
<style>
  .block-container { padding-top: 1.5rem; max-width: 1200px; }
  .disclaimer {
    background: #fff8e6; border: 1px solid #f0d9a0; border-left: 4px solid #d99a1e;
    color: #4a3a12; padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.92rem;
    margin-bottom: 1rem;
  }
  .brand { font-size: 1.6rem; font-weight: 700; color: #0f766e; margin-bottom: 0; }
  .brand-sub { color: #4b6460; margin-top: 0.1rem; }
  .who { color: #4b6460; font-size: 0.9rem; margin-top: -0.4rem; }
</style>
"""

PAGES = ["Dashboard"]  # New Scan / Patients arrive in M2


@st.cache_resource
def _init_database() -> bool:
    """Create tables once per server process, not on every rerun."""
    init_db()
    return True


def render_disclaimer() -> None:
    """Shown at the top of every screen (GUARDRAILS: always visible)."""
    st.markdown(f'<div class="disclaimer">⚕️ {DISCLAIMER}</div>', unsafe_allow_html=True)


def current_user() -> auth.AuthUser | None:
    return st.session_state.get("user")


# ---------------------------------------------------------------- auth screens

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
                                                  use_container_width=True)
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
                created = st.form_submit_button("Create account", use_container_width=True)
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

def sidebar(user: auth.AuthUser) -> str:
    with st.sidebar:
        st.markdown('<p class="brand">🫁 Screening</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="who">Signed in as <b>{user.display_name}</b></p>',
                    unsafe_allow_html=True)
        page = st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")
        st.divider()
        if st.button("Log out", use_container_width=True):
            logout()
    return page


def dashboard(user: auth.AuthUser) -> None:
    st.title(f"Welcome, {user.display_name}")
    with get_session() as s:
        n_patients = s.scalar(select(func.count(Patient.id)).where(Patient.created_by == user.id))
        n_scans = s.scalar(select(func.count(Scan.id)).where(Scan.user_id == user.id))
    c1, c2 = st.columns(2)
    c1.metric("Your patients", n_patients)
    c2.metric("Your screenings", n_scans)
    st.info("Patients, uploads and screening arrive in the next milestone (M2).")


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    _init_database()
    render_disclaimer()

    user = current_user()
    if user is None:
        login_screen()
        return

    page = sidebar(user)
    if page == "Dashboard":
        dashboard(user)


main()
