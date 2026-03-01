#!/usr/bin/env python3
"""
FILE: engine/prompts/builder.py
VERSION: 0.3
PURPOSE:
Single call site for constructing the system prompt injected into every
model call. Loads the canonical boot from disk, validates its structure,
and appends invocation parameters (role, output_mode, format).

All provider adapters (OpenAI, Gemini, Claude) must call build_system_prompt()
and pass the result as the system/instruction argument to the API.
No provider may construct its own system prompt independently.

include_schema parameter:
- False (default): strips Section 5 [BEGIN SCHEMA]...[END SCHEMA] from the boot.
  Use for Phase 1 / Phase 2 reviewer calls where the ReviewerPack schema applies.
- True: includes Section 5. Use for arena calls (judge/advocate/anti verdicts).

include_gsae parameter:
- False (default): no GSAE extraction instructions appended.
- True: appends engine/prompts/gsae_extraction.txt after the boot body,
  before invocation parameters.

FAIL-CLOSED:
- Missing boot file   → raises RuntimeError (open() propagates IOError)
- Empty boot          → raises RuntimeError
- Malformed boot      → raises RuntimeError
- Missing gsae file   → raises RuntimeError (when include_gsae=True)
- Invalid role        → raises ValueError
- Invalid output_mode → raises ValueError
"""

from __future__ import annotations

import os
import re


_BOOT_PATH = os.path.join(os.path.dirname(__file__), "survivor_boot.txt")
_GSAE_PATH = os.path.join(os.path.dirname(__file__), "gsae_extraction.txt")

_VALID_ROLES = {"judge", "advocate", "anti"}
_VALID_OUTPUT_MODES = {"machine", "reader", "dual"}

# Matches [BEGIN SCHEMA] ... [END SCHEMA] inclusive, across newlines.
_SCHEMA_BLOCK_RE = re.compile(
    r"\[BEGIN SCHEMA\].*?\[END SCHEMA\]",
    re.DOTALL,
)


def load_boot() -> str:
    """Load the canonical boot file from disk. Raises on missing or unreadable file."""
    with open(_BOOT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def build_system_prompt(
    role: str,
    output_mode: str,
    include_schema: bool = False,
    include_gsae: bool = False,
) -> str:
    """
    Build the full system prompt for a single model call.

    Parameters
    ----------
    role : str
        One of: judge | advocate | anti
    output_mode : str
        One of: machine | reader | dual
    include_schema : bool
        If False (default), Section 5 DEFINITIVE SCHEMA is stripped from the
        boot. Use False for Phase 1 / Phase 2 reviewer calls.
        If True, Section 5 is included. Use True for arena judgment calls.
    include_gsae : bool
        If True, appends GSAE extraction instructions after the boot body,
        before invocation parameters. Use True when gsae_settings.enabled.

    Returns
    -------
    str
        Complete system prompt: boot contract + (optional GSAE) + invocation parameters.

    Raises
    ------
    ValueError
        If role or output_mode is not a valid value.
    RuntimeError
        If the boot file is missing, empty, or structurally malformed.
        If include_gsae is True and the GSAE extraction file is missing.
    IOError / FileNotFoundError
        If a required file cannot be read from disk.
    """
    if role not in _VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}. Must be one of: {sorted(_VALID_ROLES)}")
    if output_mode not in _VALID_OUTPUT_MODES:
        raise ValueError(
            f"Invalid output_mode: {output_mode!r}. Must be one of: {sorted(_VALID_OUTPUT_MODES)}"
        )

    boot = load_boot()

    if not boot.strip():
        raise RuntimeError("Boot file is empty")
    if "[BEGIN BOOT" not in boot or "[END BOOT]" not in boot:
        raise RuntimeError("Boot file is malformed or incomplete (missing [BEGIN BOOT] or [END BOOT])")

    if not include_schema:
        boot = _SCHEMA_BLOCK_RE.sub("", boot).strip()

    # Optionally append GSAE extraction instructions.
    gsae_text = ""
    if include_gsae:
        with open(_GSAE_PATH, "r", encoding="utf-8") as f:
            gsae_text = f.read()
        if not gsae_text.strip():
            raise RuntimeError("GSAE extraction file is empty")

    format_spec = "json" if output_mode == "machine" else "text"

    parts = [boot]
    if gsae_text:
        parts.append(gsae_text.strip())
    parts.append(
        f"ROLE: {role}\n"
        f"OUTPUT_MODE: {output_mode}\n"
        f"FORMAT: {format_spec}"
    )

    return "\n\n".join(parts) + "\n"
