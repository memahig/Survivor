#!/usr/bin/env python3
"""
FILE: tests/test_boot_injection.py
PURPOSE:
Assert that build_system_prompt() always produces a structurally valid
boot-injected system prompt, and that all three reviewer adapters use
the builder (not inline system messages).

Run with: python -m pytest tests/ -v
"""

import ast
import os
import pytest

from engine.prompts.builder import build_system_prompt, load_boot


# ---------------------------------------------------------------------------
# Boot content tests
# ---------------------------------------------------------------------------

def test_boot_file_loads():
    boot = load_boot()
    assert boot.strip(), "Boot file must not be empty"


def test_boot_file_structure():
    boot = load_boot()
    assert "[BEGIN BOOT" in boot, "Boot must contain [BEGIN BOOT"
    assert "[END BOOT]" in boot, "Boot must contain [END BOOT]"


def test_build_system_prompt_contains_boot_markers():
    sp = build_system_prompt("judge", "machine")
    assert "[BEGIN BOOT" in sp
    assert "[END BOOT]" in sp


def test_build_system_prompt_contains_invocation_params():
    sp = build_system_prompt("judge", "machine")
    assert "ROLE:" in sp
    assert "OUTPUT_MODE:" in sp
    assert "FORMAT:" in sp


def test_build_system_prompt_machine_format_is_json():
    sp = build_system_prompt("judge", "machine")
    assert "FORMAT: json" in sp


def test_build_system_prompt_reader_format_is_text():
    sp = build_system_prompt("advocate", "reader")
    assert "FORMAT: text" in sp


def test_build_system_prompt_dual_format_is_text():
    sp = build_system_prompt("anti", "dual")
    assert "FORMAT: text" in sp


# ---------------------------------------------------------------------------
# Validation / fail-closed tests
# ---------------------------------------------------------------------------

def test_invalid_role_raises():
    with pytest.raises(ValueError, match="Invalid role"):
        build_system_prompt("wizard", "machine")


def test_invalid_output_mode_raises():
    with pytest.raises(ValueError, match="Invalid output_mode"):
        build_system_prompt("judge", "telepathy")


def test_all_valid_role_output_mode_combinations():
    for role in ("judge", "advocate", "anti"):
        for mode in ("machine", "reader", "dual"):
            sp = build_system_prompt(role, mode)
            assert "[BEGIN BOOT" in sp
            assert f"ROLE: {role}" in sp
            assert f"OUTPUT_MODE: {mode}" in sp


# ---------------------------------------------------------------------------
# include_schema parameter tests
# ---------------------------------------------------------------------------

def test_schema_excluded_by_default():
    sp = build_system_prompt("judge", "machine")
    assert "[BEGIN SCHEMA]" not in sp
    assert "[END SCHEMA]" not in sp
    assert "DEFINITIVE SCHEMA" not in sp


def test_schema_excluded_when_false():
    sp = build_system_prompt("judge", "machine", include_schema=False)
    assert "[BEGIN SCHEMA]" not in sp
    assert "DEFINITIVE SCHEMA" not in sp


def test_schema_included_when_true():
    sp = build_system_prompt("judge", "machine", include_schema=True)
    assert "[BEGIN SCHEMA]" in sp
    assert "[END SCHEMA]" in sp
    assert "DEFINITIVE SCHEMA" in sp
    assert "integrity_rating" in sp


def test_boot_invariants_present_regardless_of_schema_flag():
    for include in (True, False):
        sp = build_system_prompt("judge", "machine", include_schema=include)
        assert "[BEGIN BOOT" in sp
        assert "[END BOOT]" in sp
        assert "CONSTITUTIONAL INVARIANTS" in sp
        assert "ROLE: judge" in sp


def test_schema_strip_leaves_section_6():
    sp = build_system_prompt("judge", "machine", include_schema=False)
    assert "OPERATIONAL CONSTRAINTS" in sp


# ---------------------------------------------------------------------------
# include_gsae parameter tests
# ---------------------------------------------------------------------------

def test_gsae_excluded_by_default():
    sp = build_system_prompt("judge", "machine")
    assert "GSAE EXTRACTION" not in sp
    assert "gsae_observation" not in sp
    assert "gsae_subject" not in sp


def test_gsae_excluded_when_false():
    sp = build_system_prompt("judge", "machine", include_gsae=False)
    assert "GSAE EXTRACTION" not in sp


def test_gsae_included_when_true():
    sp = build_system_prompt("judge", "machine", include_gsae=True)
    assert "GSAE EXTRACTION" in sp
    assert "gsae_observation" in sp
    assert "gsae_subject" in sp
    assert "severity_toward_subject" in sp
    assert "severity_toward_counterparty" in sp


def test_gsae_ordering_before_invocation_params():
    """GSAE text must appear after boot body but before ROLE/OUTPUT_MODE/FORMAT."""
    sp = build_system_prompt("judge", "machine", include_gsae=True)
    gsae_pos = sp.index("GSAE EXTRACTION")
    role_pos = sp.index("ROLE: judge")
    assert gsae_pos < role_pos, "GSAE must appear before invocation params"


def test_gsae_boot_invariants_preserved():
    """Boot markers and operational constraints survive when GSAE is included."""
    sp = build_system_prompt("judge", "machine", include_gsae=True)
    assert "[BEGIN BOOT" in sp
    assert "[END BOOT]" in sp
    assert "CONSTITUTIONAL INVARIANTS" in sp
    assert "OPERATIONAL CONSTRAINTS" in sp
    assert "ROLE: judge" in sp


def test_gsae_with_schema_both_present():
    """include_gsae=True + include_schema=True includes both."""
    sp = build_system_prompt("judge", "machine", include_schema=True, include_gsae=True)
    assert "DEFINITIVE SCHEMA" in sp
    assert "GSAE EXTRACTION" in sp


# ---------------------------------------------------------------------------
# Adapter compliance: no inline system messages
# ---------------------------------------------------------------------------

REVIEWERS_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "reviewers")

INLINE_SYSTEM_PATTERNS = [
    "Return only strict JSON",
    "No markdown. No commentary.",
    "system_msg =",
    "full_prompt = \"Return",
]

REVIEWER_FILES = ["claude_reviewer.py", "openai_reviewer.py", "gemini_reviewer.py"]


@pytest.mark.parametrize("filename", REVIEWER_FILES)
def test_no_inline_system_message(filename):
    path = os.path.join(REVIEWERS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    for pattern in INLINE_SYSTEM_PATTERNS:
        assert pattern not in source, (
            f"{filename} contains banned inline system message pattern: {repr(pattern)}"
        )


@pytest.mark.parametrize("filename", REVIEWER_FILES)
def test_adapter_imports_build_system_prompt(filename):
    path = os.path.join(REVIEWERS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    assert "build_system_prompt" in source, (
        f"{filename} must import and use build_system_prompt"
    )


@pytest.mark.parametrize("filename", REVIEWER_FILES)
def test_adapter_calls_build_system_prompt_in_run_methods(filename):
    path = os.path.join(REVIEWERS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    # Both run_phase1 and run_phase2 must reference build_system_prompt
    count = source.count("build_system_prompt(")
    assert count >= 2, (
        f"{filename} must call build_system_prompt() in both run_phase1 and run_phase2 "
        f"(found {count} call(s))"
    )


@pytest.mark.parametrize("filename", REVIEWER_FILES)
def test_adapter_passes_include_gsae(filename):
    """All real reviewer adapters must pass include_gsae to build_system_prompt."""
    path = os.path.join(REVIEWERS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    assert "include_gsae=" in source, (
        f"{filename} must pass include_gsae to build_system_prompt()"
    )
