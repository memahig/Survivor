#!/usr/bin/env python3
"""
FILE: tests/test_gsae_process.py
PURPOSE:
Tests for engine/eo/gsae_process.py — GSAE Tier C runner.

Run with: python -m pytest tests/ -v
"""

from engine.eo.gsae_process import run_gsae_tier_c


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_GSAE_SETTINGS = {
    "enabled": True,
    "epsilon": 0.1,
    "tau": 0.25,
    "weights": {
        "classification_bucket": 0.25,
        "intent_level": 0.25,
        "severity_tier": 0.2,
        "requires_corrob": 0.1,
        "omission_load_bearing": 0.1,
        "confidence_band": 0.1,
    },
    "version": "0.2",
}

_VALID_OBSERVATION = {
    "classification_bucket": "reporting",
    "intent_level": "none",
    "requires_corrob": False,
    "omission_load_bearing": False,
    "severity_tier": "minimal",
    "confidence_band": "sb_low",
}


def _make_pack(reviewer, observation=None):
    pack = {
        "reviewer": reviewer,
        "whole_article_judgment": {"classification": "analysis", "confidence": "high", "evidence_eids": ["E1"]},
        "main_conclusion": {"text": "X."},
        "pillar_claims": [],
        "questionable_claims": [],
        "background_claims_summary": {"total_claims_estimate": 0, "not_triaged_count": 0},
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


def test_enabled_with_observation_returns_gsae_block():
    """Enabled + one observation → returns gsae dict with PASS artifact (null swap)."""
    config = {"gsae_settings": _GSAE_SETTINGS}
    phase2 = {
        "openai": _make_pack("openai", observation=dict(_VALID_OBSERVATION)),
    }

    result = run_gsae_tier_c(phase2, config)

    assert result is not None
    assert "settings" in result
    assert "packet_pairs" in result
    assert "artifacts" in result

    assert len(result["packet_pairs"]) == 1
    assert len(result["artifacts"]) == 1

    pair = result["packet_pairs"][0]
    assert pair["packet_a"] == pair["packet_b"]  # null swap

    art = result["artifacts"][0]
    assert art["symmetry_status"] == "PASS"
    assert art["delta"] == 0.0
    assert art["soft_symmetry_flag"] is False
    assert art["quarantine_fields"] == []


def test_enabled_no_observations_returns_none():
    """Enabled + no gsae_observation in any pack → returns None."""
    config = {"gsae_settings": _GSAE_SETTINGS}
    phase2 = {
        "openai": _make_pack("openai"),
        "gemini": _make_pack("gemini"),
    }

    result = run_gsae_tier_c(phase2, config)
    assert result is None


def test_disabled_returns_none():
    """GSAE disabled in config → returns None regardless of observations."""
    config = {"gsae_settings": {**_GSAE_SETTINGS, "enabled": False}}
    phase2 = {
        "openai": _make_pack("openai", observation=dict(_VALID_OBSERVATION)),
    }

    result = run_gsae_tier_c(phase2, config)
    assert result is None


# ---------------------------------------------------------------------------
# v0.3 directional swap tests
# ---------------------------------------------------------------------------

_GSAE_SETTINGS_V03 = {
    "enabled": True,
    "epsilon": 0.0,
    "tau": 0.25,
    "weights": {
        "classification_bucket": 0.10,
        "intent_level": 0.10,
        "requires_corrob": 0.10,
        "omission_load_bearing": 0.10,
        "severity_toward_subject": 0.25,
        "severity_toward_counterparty": 0.25,
        "confidence_band": 0.10,
    },
    "version": "0.3",
}

_V03_ASYMMETRIC_OBS = {
    "classification_bucket": "reporting",
    "intent_level": "none",
    "requires_corrob": False,
    "omission_load_bearing": False,
    "severity_toward_subject": "high",
    "severity_toward_counterparty": "minimal",
    "confidence_band": "sb_low",
}


def test_v03_asymmetric_yields_nonzero_delta():
    """Asymmetric v0.3 observation produces delta>0 after directional swap."""
    config = {"gsae_settings": _GSAE_SETTINGS_V03}
    phase2 = {
        "openai": _make_pack("openai", observation=dict(_V03_ASYMMETRIC_OBS)),
    }

    result = run_gsae_tier_c(phase2, config)

    assert result is not None
    assert len(result["packet_pairs"]) == 1
    assert len(result["artifacts"]) == 1

    pair = result["packet_pairs"][0]
    a = pair["packet_a"]
    b = pair["packet_b"]

    # Swap must flip directional severity
    assert a["severity_toward_subject"] == b["severity_toward_counterparty"]
    assert a["severity_toward_counterparty"] == b["severity_toward_subject"]

    art = result["artifacts"][0]
    assert art["delta"] is not None
    assert art["delta"] > 0.0


def test_v03_symmetric_yields_zero_delta():
    """Symmetric v0.3 observation produces delta=0 after swap (both sides equal)."""
    symmetric_obs = {
        "classification_bucket": "reporting",
        "intent_level": "none",
        "requires_corrob": False,
        "omission_load_bearing": False,
        "severity_toward_subject": "moderate",
        "severity_toward_counterparty": "moderate",
        "confidence_band": "sb_low",
    }
    config = {"gsae_settings": _GSAE_SETTINGS_V03}
    phase2 = {
        "openai": _make_pack("openai", observation=dict(symmetric_obs)),
    }

    result = run_gsae_tier_c(phase2, config)

    assert result is not None
    art = result["artifacts"][0]
    assert art["symmetry_status"] == "PASS"
    assert art["delta"] == 0.0
