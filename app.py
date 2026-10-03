"""Pneumonia Screening — Streamlit entry point.

Decision: all UI lives here (per CLAUDE.md); data/auth/ML live in their own
modules so they stay testable without Streamlit. Routing is a simple
session_state key rather than Streamlit multipage, so the login gate and the
always-on disclaimer are enforced in exactly one place.
"""
import streamlit as st

st.set_page_config(
    page_title="Pneumonia Screening",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="auto",
)

DISCLAIMER = (
    "**Decision-support only — not a diagnosis.** This tool gives a screening "
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
</style>
"""


def render_disclaimer() -> None:
    """Shown at the top of every screen (GUARDRAILS: always visible)."""
    st.markdown(
        f'<div class="disclaimer">⚕️ {DISCLAIMER.replace("**", "")}</div>',
        unsafe_allow_html=True,
    )


def login_screen() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<p class="brand">🫁 Pneumonia Screening</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="brand-sub">Chest X-ray decision-support for clinicians</p>',
            unsafe_allow_html=True,
        )
        with st.form("login"):
            st.text_input("Username")
            st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            st.info("Authentication is wired up in milestone M1.")


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    render_disclaimer()
    login_screen()


main()
