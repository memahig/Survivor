#!/usr/bin/env python3
"""
FILE: streamlit_app.py
VERSION: 0.2
PURPOSE:
Streamlit UI for Survivor — The Blunt Report.
Single page. No tabs. Blunt narrative first, technical details in expander.

ARCHITECTURE:
- Calls engine.core.pipeline.run_pipeline() with a temp directory.
- Renders Blunt narrative via engine.render.blunt_biaslens.
- Falls back to technical report.md if Blunt renderer fails.
- Password-gated via dual-source: st.secrets (Cloud) or .env (local).
"""

from __future__ import annotations

import json
import os
import tempfile

from dotenv import load_dotenv
import streamlit as st

load_dotenv()  # load .env for local runs; no-op if absent

BUILD_ID = "SURVIVOR_2026-03-01"


# -----------------------------
# UI config
# -----------------------------
st.set_page_config(page_title="The Blunt Report", page_icon="🛡️", layout="wide")


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

    st.title("The Blunt Report")
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

st.title("The Blunt Report")
st.caption(f"Build: {BUILD_ID} | auth: ok")
st.write("A multi-reviewer pipeline that reports what can be responsibly recovered from an article.")

# Logout in sidebar (minimal)
with st.sidebar:
    if st.session_state.get("authenticated"):
        if st.button("Logout", use_container_width=True):
            st.session_state.pop("authenticated", None)
            st.session_state.pop("_auth_pwd", None)
            st.rerun()


# -----------------------------
# Input — single radio, one input, one button
# -----------------------------
mode = st.radio("Input", ["URL", "Paste text"], horizontal=True)

url = ""
raw_text = ""
if mode == "URL":
    url = st.text_input("Article URL", value="", placeholder="https://...")
else:
    raw_text = st.text_area(
        "Paste article body text",
        height=260,
        placeholder="Paste the full article text here (not the URL).",
    )

go = st.button("Run", use_container_width=True)


# -----------------------------
# Pipeline runner
# -----------------------------
def _run_survivor(*, url: str | None = None, text_content: str | None = None) -> None:
    """Run the Survivor pipeline and display the Blunt Report."""
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

            # Read back generated files
            report_path = os.path.join(tmpdir, "report.md")
            debug_path = os.path.join(tmpdir, "debug.md")
            run_json_path = os.path.join(tmpdir, "run.json")

            report_md = None
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    report_md = f.read()

            debug_md = None
            if os.path.exists(debug_path):
                with open(debug_path, "r", encoding="utf-8") as f:
                    debug_md = f.read()

            run_json_str = None
            run_state = None
            if os.path.exists(run_json_path):
                with open(run_json_path, "r", encoding="utf-8") as f:
                    run_json_str = f.read()
                try:
                    run_state = json.loads(run_json_str)
                except json.JSONDecodeError:
                    run_state = None

    # ---- Render Blunt Report first ----
    blunt_md = None
    if run_state is not None:
        try:
            from engine.render.blunt_biaslens import render_blunt_biaslens
            blunt_md = render_blunt_biaslens(run_state, config={})
        except Exception:
            blunt_md = None

    st.success("Done.")

    if blunt_md:
        st.markdown(blunt_md)
    else:
        st.info("Blunt report renderer not available. Showing technical report below.")
        if report_md:
            st.markdown(report_md)
        else:
            st.error("No report was generated.")
            return

    # ---- Technical details in expander ----
    with st.expander("Technical details", expanded=False):
        if report_md:
            st.markdown(report_md)
        if debug_md:
            st.markdown("\n---\n")
            st.markdown(debug_md)
        if run_json_str:
            st.markdown("\n---\n")
            st.code(run_json_str, language="json")


# -----------------------------
# Run
# -----------------------------
if go:
    if mode == "URL":
        u = (url or "").strip()
        if not u:
            st.warning("Please enter a URL.")
        else:
            _run_survivor(url=u)
    else:
        t = (raw_text or "").strip()
        if not t:
            st.warning("Please paste some article text.")
        else:
            _run_survivor(text_content=t)
