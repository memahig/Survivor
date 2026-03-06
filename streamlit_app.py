#!/usr/bin/env python3
"""
FILE: streamlit_app.py
VERSION: 0.5
PURPOSE:
Streamlit UI for Survivor — The Blunt Report.
Three tabs: Blunt Report | Audit Report | Machine Trace.

ARCHITECTURE:
- Calls engine.core.pipeline.run_pipeline() with a temp directory.
- Renders via engine.render.render_bundle.render_all().
- Falls back to technical report.md if Blunt renderer fails.
- Surfaces renderer errors as warnings (never silently swallows).
- Password-gated via dual-source: st.secrets (Cloud) or .env (local).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from dotenv import load_dotenv
import streamlit as st

load_dotenv()  # load .env for local runs; no-op if absent

# Bridge: Streamlit Cloud secrets → os.environ (engine uses os.getenv)
_SECRET_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
try:
    for _k in _SECRET_KEYS:
        if _k in st.secrets and _k not in os.environ:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass  # st.secrets unavailable (local run) — .env handles it


def _get_build_id() -> str:
    """Live git SHA stamp — proves which commit Streamlit Cloud is running."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return f"SURVIVOR_{sha}"
    except Exception:
        return "SURVIVOR_unknown"


BUILD_ID = _get_build_id()


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

# Sidebar: logout + debug toggles
with st.sidebar:
    if st.session_state.get("authenticated"):
        if st.button("Logout", use_container_width=True):
            st.session_state.pop("authenticated", None)
            st.session_state.pop("_auth_pwd", None)
            st.rerun()
    st.markdown("---")


# -----------------------------
# Input — single radio, one input, one button
# -----------------------------
mode = st.radio("Input", ["URL", "Paste / upload text"], horizontal=True)

url = ""
raw_text = ""
if mode == "URL":
    url = st.text_input("Article URL", value="", placeholder="https://...")
else:
    pasted = st.text_area(
        "Paste article text",
        height=260,
        placeholder="Paste the full article text here (.txt or .md).",
    )
    uploaded = st.file_uploader(
        "Or upload a file (.txt or .md)",
        type=["txt", "md"],
    )
    if pasted.strip():
        raw_text = pasted
    elif uploaded is not None:
        raw_text = uploaded.read().decode("utf-8", errors="replace")

go = st.button("Run", use_container_width=True)


# -----------------------------
# Pipeline runner
# -----------------------------
def _run_survivor(*, url: str | None = None, text_content: str | None = None) -> None:
    """Run the Survivor pipeline and display the Blunt Report."""
    status = st.empty()
    detail = st.empty()

    report_md = None
    run_json_str = None
    run_state = None
    blunt_md = None
    audit_md = None
    enriched = None
    render_err = None

    try:
        status.info("Importing pipeline...")
        from engine.core.pipeline import run_pipeline

        with tempfile.TemporaryDirectory(prefix="survivor_") as tmpdir:
            status.info("Preparing temp workspace...")
            textfile_path = None

            if text_content:
                textfile_path = os.path.join(tmpdir, "input.txt")
                with open(textfile_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

            status.info("Running Survivor pipeline...")
            try:
                run_pipeline(
                    url=url,
                    textfile=textfile_path,
                    outdir=tmpdir,
                )
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                compile_err_path = os.path.join(tmpdir, "compile_error.json")
                if os.path.exists(compile_err_path):
                    try:
                        with open(compile_err_path, "r", encoding="utf-8") as _f:
                            _ced = json.load(_f)
                        with st.expander("Compile error detail", expanded=True):
                            st.write(f"**Reviewer:** {_ced.get('reviewer_id')} | **Attempt:** {_ced.get('attempt')}")
                            st.subheader("Validation errors")
                            st.json(_ced.get("validation_errors", []))
                            st.subheader("Translation trace")
                            st.json(_ced.get("translation_trace", []))
                    except Exception as _read_err:
                        st.warning(f"Could not read compile_error.json: {_read_err}")
                return

            status.info("Pipeline finished. Reading outputs...")

            report_path = os.path.join(tmpdir, "report.md")
            run_json_path = os.path.join(tmpdir, "run.json")

            detail.code(
                json.dumps(
                    {
                        "report_exists": os.path.exists(report_path),
                        "run_json_exists": os.path.exists(run_json_path),
                        "tmpdir": tmpdir,
                    },
                    indent=2,
                ),
                language="json",
            )

            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    report_md = f.read()

            if os.path.exists(run_json_path):
                with open(run_json_path, "r", encoding="utf-8") as f:
                    run_json_str = f.read()
                try:
                    run_state = json.loads(run_json_str)
                except json.JSONDecodeError as e:
                    st.error(f"run.json exists but could not be parsed: {e}")
                    st.code(run_json_str[:4000])
                    return

        status.info("Rendering reports...")
        if run_state is not None:
            from engine.render.render_bundle import render_all
            blunt_md, audit_md, enriched, render_err = render_all(run_state, config={})
        else:
            st.warning("Pipeline completed but no run_state was loaded.")

    except Exception as e:
        st.error(f"App-stage error: {e}")
        return

    status.success("Done.")

    tab1, tab2, tab3 = st.tabs(["Blunt Report", "Audit Report", "Machine Trace"])

    with tab1:
        if blunt_md:
            st.markdown(blunt_md)
        elif report_md:
            st.info("Blunt Report not available. Showing technical report.")
            st.markdown(report_md)
        else:
            st.info("Blunt Report not available.")

    with tab2:
        if audit_md:
            st.markdown(audit_md)
        else:
            st.info("Audit Report not available.")

    with tab3:
        if enriched is not None:
            st.code(json.dumps(enriched, indent=2, default=str), language="json")
        elif run_json_str:
            st.code(run_json_str, language="json")
        else:
            st.info("Machine Trace not available.")

    if render_err:
        st.warning(f"Renderer warnings: {render_err}")


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
            st.warning("Please paste text or upload a .txt / .md file.")
        else:
            _run_survivor(text_content=t)
