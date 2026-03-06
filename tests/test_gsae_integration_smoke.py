#!/usr/bin/env python3
"""
FILE: tests/test_gsae_integration_smoke.py
PURPOSE:
Deterministic integration smoke: Tier C produces QUARANTINE and the
quarantine adapter prunes gsae_observation before adjudication.

This is intentionally "pipeline slice" style: we validate the contract
between run_gsae_tier_c() and apply_gsae_quarantine() without any live LLM calls.
"""

from engine.eo.gsae_process import run_gsae_tier_c
from engine.eo.gsae_apply import apply_gsae_quarantine


_V03_ASYMMETRIC = {
    "classification_bucket": "reporting",
    "intent_level": "none",
    "requires_corrob": False,
    "omission_load_bearing": False,
    "severity_toward_subject": "high",
    "severity_toward_counterparty": "minimal",
    "confidence_band": "sb_high",
}

_V03_SYMMETRIC = {
    "classification_bucket": "reporting",
    "intent_level": "none",
    "requires_corrob": False,
    "omission_load_bearing": False,
    "severity_toward_subject": "low",
    "severity_toward_counterparty": "low",
    "confidence_band": "sb_high",
}


def _make_pack(reviewer: str, observation=None) -> dict:
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


def test_gsae_quarantine_prunes_before_adjudication_slice():
    """End-to-end Tier C → Enforcer: QUARANTINE prunes gsae_observation on sanitized copy."""
    # Config tuned to ensure QUARANTINE triggers for the asymmetric packet.
    config = {
        "gsae_settings": {
            "enabled": True,
            "epsilon": 0.1,
            "tau": 0.25,
            "version": "0.3",
            "weights": {
                "classification_bucket": 0.10,
                "intent_level": 0.10,
                "requires_corrob": 0.10,
                "omission_load_bearing": 0.10,
                "severity_toward_subject": 0.25,
                "severity_toward_counterparty": 0.25,
                "confidence_band": 0.10,
            },
        }
    }

    # Sorted reviewer keys determine artifact ordering in extract_gsae_observations().
    phase2_outputs = {
        "gemini": _make_pack("gemini", observation=dict(_V03_SYMMETRIC)),      # should PASS
        "openai": _make_pack("openai", observation=dict(_V03_ASYMMETRIC)),     # should QUARANTINE
    }

    gsae_block = run_gsae_tier_c(phase2_outputs, config)
    assert gsae_block is not None
    assert "artifacts" in gsae_block
    assert len(gsae_block["artifacts"]) == 2  # one per reviewer with observation

    # Expect ordering: gemini first, openai second (sorted keys)
    assert gsae_block["artifacts"][0]["symmetry_status"] in ("PASS", "SOFT_FLAG", "QUARANTINE")
    assert gsae_block["artifacts"][1]["symmetry_status"] in ("PASS", "SOFT_FLAG", "QUARANTINE")

    # We specifically want the asymmetric one to QUARANTINE (openai index 1).
    assert gsae_block["artifacts"][1]["symmetry_status"] == "QUARANTINE"

    phase2_sanitized = apply_gsae_quarantine(phase2_outputs, gsae_block, config)

    # Original untouched (audit trail)
    assert "gsae_observation" in phase2_outputs["openai"]
    assert "gsae_observation" in phase2_outputs["gemini"]

    # Sanitized: quarantined reviewer loses the block
    assert "gsae_observation" not in phase2_sanitized["openai"]

    # Non-quarantined reviewer remains intact
    assert "gsae_observation" in phase2_sanitized["gemini"]
