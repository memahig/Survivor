#!/usr/bin/env python3
"""
FILE: tests/test_gsae_packets.py
PURPOSE:
Tests for engine/eo/gsae_packets.py — GSAE observation extraction.

Run with: python -m pytest tests/ -v
"""

from engine.eo.gsae_packets import extract_gsae_observations


# ---------------------------------------------------------------------------
# Minimal pack fixtures (only keys relevant to extraction)
# ---------------------------------------------------------------------------

def _make_pack(reviewer, with_observation=False):
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
    if with_observation:
        pack["gsae_observation"] = {
            "classification_bucket": "reporting",
            "intent_level": "none",
            "requires_corrob": False,
            "omission_load_bearing": False,
            "severity_tier": "minimal",
            "confidence_band": "sb_low",
        }
    return pack


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_mixed_packs_extracts_only_present():
    """One pack with gsae_observation, one without → returns length 1."""
    phase2 = {
        "openai": _make_pack("openai", with_observation=True),
        "gemini": _make_pack("gemini", with_observation=False),
    }
    result = extract_gsae_observations(phase2)
    assert len(result) == 1
    assert result[0]["reviewer"] == "openai"
    assert set(result[0].keys()) == {"reviewer", "observation"}
    assert result[0]["observation"]["classification_bucket"] == "reporting"


def test_no_observations_returns_empty():
    """Packs without gsae_observation → returns []."""
    phase2 = {
        "openai": _make_pack("openai"),
        "gemini": _make_pack("gemini"),
    }
    result = extract_gsae_observations(phase2)
    assert result == []
