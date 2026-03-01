#!/usr/bin/env python3
"""
FILE: tests/test_gsae_apply.py
PURPOSE:
Tests for engine/eo/gsae_apply.py — GSAE quarantine application.

Run with: python -m pytest tests/ -v
"""

from engine.eo.gsae_apply import apply_gsae_quarantine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_V03_OBSERVATION = {
    "classification_bucket": "reporting",
    "intent_level": "none",
    "requires_corrob": False,
    "omission_load_bearing": False,
    "severity_toward_subject": "high",
    "severity_toward_counterparty": "minimal",
    "confidence_band": "sb_low",
}


def _make_pack(reviewer, observation=None):
    pack = {
        "reviewer": reviewer,
        "whole_article_judgment": {"classification": "analysis", "confidence": "high", "evidence_eids": ["E1"]},
        "main_conclusion": {"text": "X."},
        "claims": [],
        "scope_markers": [],
        "causal_links": [],
        "article_patterns": [],
        "omission_candidates": [],
        "counterfactual_requirements": [],
        "evidence_density": {"claims_count": 0, "claims_with_internal_support": 0, "external_sources_count": 0},
        "claim_tickets": [],
        "article_tickets": [],
        "cross_claim_votes": [],
    }
    if observation is not None:
        pack["gsae_observation"] = observation
    return pack


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_quarantine_no_change():
    """When gsae_block is None, phase2_outputs are returned unchanged."""
    phase2 = {
        "openai": _make_pack("openai", observation=dict(_V03_OBSERVATION)),
        "gemini": _make_pack("gemini"),
    }
    config = {}

    result = apply_gsae_quarantine(phase2, None, config)

    assert result is phase2  # exact same object, not a copy


def test_quarantine_removes_observation():
    """QUARANTINE artifact removes gsae_observation from that reviewer's pack."""
    phase2 = {
        "openai": _make_pack("openai", observation=dict(_V03_OBSERVATION)),
    }
    config = {}

    gsae_block = {
        "settings": {},
        "packet_pairs": [
            {"packet_a": dict(_V03_OBSERVATION), "packet_b": dict(_V03_OBSERVATION)},
        ],
        "artifacts": [
            {
                "symmetry_status": "QUARANTINE",
                "delta": 0.5,
                "soft_symmetry_flag": False,
                "quarantine_fields": ["severity_toward_subject"],
            },
        ],
    }

    result = apply_gsae_quarantine(phase2, gsae_block, config)

    # Original must NOT be mutated
    assert "gsae_observation" in phase2["openai"]

    # Sanitized copy must have observation removed
    assert "gsae_observation" not in result["openai"]

    # Rest of the pack must still be intact
    assert result["openai"]["reviewer"] == "openai"
    assert result["openai"]["claims"] == []


def test_quarantine_others_unaffected():
    """Only quarantined reviewer loses observation; others keep theirs."""
    obs_openai = dict(_V03_OBSERVATION)
    obs_gemini = dict(_V03_OBSERVATION)
    obs_gemini["severity_toward_subject"] = "minimal"  # symmetric, will PASS

    phase2 = {
        "gemini": _make_pack("gemini", observation=obs_gemini),
        "openai": _make_pack("openai", observation=obs_openai),
    }
    config = {}

    # Artifacts in sorted order: gemini(index 0), openai(index 1)
    # Only openai (index 1) is quarantined
    gsae_block = {
        "settings": {},
        "packet_pairs": [
            {"packet_a": obs_gemini, "packet_b": obs_gemini},
            {"packet_a": obs_openai, "packet_b": obs_openai},
        ],
        "artifacts": [
            {
                "symmetry_status": "PASS",
                "delta": 0.0,
                "soft_symmetry_flag": False,
                "quarantine_fields": [],
            },
            {
                "symmetry_status": "QUARANTINE",
                "delta": 0.5,
                "soft_symmetry_flag": False,
                "quarantine_fields": ["severity_toward_subject"],
            },
        ],
    }

    result = apply_gsae_quarantine(phase2, gsae_block, config)

    # Gemini (PASS) keeps observation
    assert "gsae_observation" in result["gemini"]

    # OpenAI (QUARANTINE) loses observation
    assert "gsae_observation" not in result["openai"]

    # Originals untouched
    assert "gsae_observation" in phase2["openai"]
    assert "gsae_observation" in phase2["gemini"]
