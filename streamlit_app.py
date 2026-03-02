#!/usr/bin/env python3
"""
FILE: streamlit_app.py
VERSION: 0.1
PURPOSE:
Streamlit UI for Survivor — epistemic integrity pipeline.
Runs the full pipeline on a URL or pasted article text and renders the report.

ARCHITECTURE:
- Calls engine.core.pipeline.run_pipeline() with a temp directory.
- Reads back report.md and displays it.
- Password-gated via dual-source: st.secrets (Cloud) or .env (local).
"""

from __future__ import annotations

import os
import tempfile

from dotenv import load_dotenv
import streamlit as st

load_dotenv()  # load .env for local runs; no-op if absent

BUILD_ID = "SURVIVOR_2026-03-01"


# -----------------------------
# UI config
# -----------------------------
st.set_page_config(page_title="Survivor", page_icon="🛡️", layout="wide")


# -----------------------------
# Auth gate — runs before ANY content renders
# -----------------------------
def _get_app_password() -> str | None:
    """Dual-source password: Streamlit Secrets (Cloud) first, .env fallback (local)."""
    try:
        if "APP_PASSWORD" in st.secrets:
            return st.secrets["APP_PASSWORD"]
    except Exception:
        pass
    return os.getenv("APP_PASSWORD")


def _require_password() -> None:
    """Block all page content until the correct password is provided."""
    if st.session_state.get("authenticated"):
        return

    st.title("🛡️ Survivor")
    st.markdown("**Access restricted.** Enter the password to continue.")
    st.caption("auth: waiting")
    pwd = st.text_input("Password", type="password", key="_auth_pwd")

    if st.button("Log in", use_container_width=True):
        correct = _get_app_password()
        if correct is None:
            st.error("APP_PASSWORD is not configured (check Streamlit Secrets or .env).")
            st.stop()

        if pwd == correct:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


_require_password()

st.title("🛡️ Survivor — Epistemic Integrity Pipeline")
st.caption(f"Build: {BUILD_ID} | auth: ok")
st.caption("Multi-reviewer, evidence-indexed article analysis with GSAE symmetry enforcement.")

with st.sidebar:
    st.header("Options")
    show_debug = st.checkbox("Show debug report", value=False)
    show_json = st.checkbox("Show raw run.json", value=False)

    st.divider()
    if st.session_state.get("authenticated"):
        if st.button("Logout", use_container_width=True):
            st.session_state.pop("authenticated", None)
            st.session_state.pop("_auth_pwd", None)
            st.rerun()

tab_url, tab_text = st.tabs(["Analyze URL", "Paste Text"])


# -----------------------------
# Pipeline runner
# -----------------------------
def _run_survivor(*, url: str | None = None, text_content: str | None = None) -> None:
    """Run the Survivor pipeline and display the report."""
    with st.spinner("Running Survivor pipeline (this may take 1-2 minutes)..."):
        try:
            from engine.core.pipeline import run_pipeline
        except ImportError as e:
            st.error(f"Failed to import Survivor engine: {e}")
            return

        with tempfile.TemporaryDirectory(prefix="survivor_") as tmpdir:
            textfile_path = None

            if text_content:
                textfile_path = os.path.join(tmpdir, "input.txt")
                with open(textfile_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

            try:
                run_pipeline(
                    url=url,
                    textfile=textfile_path,
                    outdir=tmpdir,
                )
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                return

            # Read back generated reports
            report_path = os.path.join(tmpdir, "report.md")
            debug_path = os.path.join(tmpdir, "debug.md")
            run_json_path = os.path.join(tmpdir, "run.json")

            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    report_md = f.read()
            else:
                st.error("Pipeline completed but report.md was not generated.")
                return

            debug_md = None
            if show_debug and os.path.exists(debug_path):
                with open(debug_path, "r", encoding="utf-8") as f:
                    debug_md = f.read()

            run_json = None
            if show_json and os.path.exists(run_json_path):
                with open(run_json_path, "r", encoding="utf-8") as f:
                    run_json = f.read()

    # Render outside the spinner
    st.success("Pipeline complete.")
    st.markdown(report_md)

    if debug_md:
        with st.expander("Debug Report", expanded=False):
            st.markdown(debug_md)

    if run_json:
        with st.expander("Raw run.json", expanded=False):
            st.code(run_json, language="json")


# -----------------------------
# Tab: URL
# -----------------------------
with tab_url:
    url = st.text_input("Article URL", value="", placeholder="https://...")
    go_url = st.button("Analyze URL", use_container_width=True, key="go_url")

    if go_url:
        u = (url or "").strip()
        if not u:
            st.warning("Please enter a URL.")
        else:
            _run_survivor(url=u)


# -----------------------------
# Tab: Paste Text
# -----------------------------
with tab_text:
    raw_text = st.text_area(
        "Paste article body text",
        height=300,
        placeholder="Paste the full article text here (not the URL).",
    )
    go_text = st.button("Analyze pasted text", use_container_width=True, key="go_text")

    if go_text:
        article_text = (raw_text or "").strip()
        if not article_text:
            st.warning("Please paste some article text.")
        else:
            _run_survivor(text_content=article_text)
