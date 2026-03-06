#!/usr/bin/env python3
"""
FILE: tests/test_report_rendering.py
PURPOSE:
Rendering tests for engine.render.report.render_report(), focused on GSAE section visibility
and deterministic reviewer-to-artifact mapping.

CONTRACT:
- Deterministic and offline: no network, no model calls, no file IO.
"""

from engine.render.report import render_report


def _base_run_state() -> dict:
    return {
        "article": {"id": "A1", "title": "T", "source_url": "https://example.com"},
        "evidence_bank": {"items": [], "used_chars": 0},
        "phase2": {},
        "adjudicated": {
            "article_track": {"adjudicated_whole_article_judgment": {"classification": "reporting", "confidence": "high", "evidence_eids": []}},
            "claim_track": {"arena": {"groups_count": 0, "edges": [], "adjudicated_claims": []}},
            "final_tickets": [],
        },
        "verification": {"enabled": False},
    }


def _pack(with_observation: bool = False, with_subject: bool = False) -> dict:
    p = {
        "reviewer": "x",
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
        p["gsae_observation"] = {
            "classification_bucket": "reporting",
            "intent_level": "none",
            "requires_corrob": False,
            "omission_load_bearing": False,
            "severity_toward_subject": "high",
            "severity_toward_counterparty": "minimal",
            "confidence_band": "sb_high",
        }
    if with_subject:
        p["gsae_subject"] = {"subject_label": "Israel", "subject_role": "actor_primary", "counterparty_label": "Iran"}
    return p


def test_render_report_no_gsae_block_has_no_gsae_section():
    run_state = _base_run_state()
    run_state["phase2"] = {"openai": _pack(), "gemini": _pack()}
    md = render_report(run_state, config={})
    assert "## GSAE Symmetry (Tier C)" not in md


def test_render_report_with_gsae_block_renders_statuses_and_mapping():
    """
    Deterministic mapping contract:
    artifact index corresponds to sorted reviewers with gsae_observation.
    Here: gemini + openai both have observation -> obs_reviewers = ['gemini','openai'].
    artifacts[0] -> gemini, artifacts[1] -> openai.
    """
    run_state = _base_run_state()
    run_state["phase2"] = {
        "openai": _pack(with_observation=True),
        "gemini": _pack(with_observation=True),
    }
    run_state["gsae"] = {
        "settings": {"version": "0.3", "epsilon": 0.1, "tau": 0.25},
        "artifacts": [
            {"symmetry_status": "PASS", "delta": 0.0, "quarantine_fields": []},  # gemini
            {"symmetry_status": "QUARANTINE", "delta": 0.375, "quarantine_fields": ["gsae_observation"]},  # openai
        ],
    }
    md = render_report(run_state, config={})

    assert "## GSAE Symmetry (Tier C)" in md
    assert "version=0.3" in md
    assert "| gemini | yes | PASS" in md
    assert "| openai | yes | QUARANTINE" in md
    assert "### Quarantine log" in md
    assert "quarantined_reviewers: ['openai']" in md


def test_render_report_lists_reviewers_without_observation():
    run_state = _base_run_state()
    run_state["phase2"] = {
        "openai": _pack(with_observation=True, with_subject=True),
        "gemini": _pack(with_observation=False),
    }
    run_state["gsae"] = {
        "settings": {"version": "0.3", "epsilon": 0.1, "tau": 0.25},
        "artifacts": [
            {"symmetry_status": "SOFT_FLAG", "delta": 0.2, "quarantine_fields": []},  # openai (only one obs reviewer)
        ],
    }
    md = render_report(run_state, config={})

    # GSAE subject context appears (if any pack has gsae_subject)
    assert "subject: Israel | counterparty: Iran" in md

    # Reviewer without observation is explicitly present with has_observation=no and status=--
    assert "| gemini | no | -- | -- | -- |" in md
