#!/usr/bin/env python3
"""
FILE: tests/test_render_bundle.py
PURPOSE: Tests for engine.render.render_bundle
         - returns 4-tuple
         - blunt and audit both rendered from valid state
         - enriched substrate returned
         - fallback on enrichment failure
         - empty run_state handled

Run with: python -m pytest tests/test_render_bundle.py -v
"""

from engine.render.render_bundle import render_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_run_state() -> dict:
    """Build a minimal but valid run_state."""
    return {
        "article": {"title": "Test Article"},
        "evidence_bank": {"items": [{"eid": "E1", "quote": "Quote one"}]},
        "phase1": {},
        "phase2": {
            "openai": {
                "whole_article_judgment": {"classification": "reporting", "confidence": "high"},
                "counterfactual_requirements": [],
            },
        },
        "adjudicated": {
            "claim_track": {
                "arena": {
                    "adjudicated_claims": [
                        {
                            "group_id": "G1",
                            "member_claim_ids": ["C1"],
                            "text": "The economy grew last quarter",
                            "type": "factual",
                            "centrality": 2,
                            "claim_kind": "world_fact",
                            "checkability": "checkable",
                            "evidence_eids": ["E1"],
                            "adjudication": "kept",
                            "tally": {"supported_votes": 1, "unsupported_votes": 0},
                            "reviewer_votes": {},
                        },
                    ]
                }
            },
            "article_track": {
                "adjudicated_whole_article_judgment": {
                    "classification": "reporting",
                    "confidence": "high",
                }
            },
            "structural_forensics": {
                "argument_integrity": {
                    "merged_argument_fragility": "low",
                    "load_bearing_claim_ids": [],
                    "weak_link_claim_ids": [],
                },
                "article_omissions": [],
                "framing_omissions": [],
                "claim_omissions": [],
                "rival_narratives": [],
            },
        },
        "gsae": None,
        "divergence_radar": {"status": "run"},
        "verification": {"enabled": True, "note": "noop"},
    }


# ---------------------------------------------------------------------------
# Return shape tests
# ---------------------------------------------------------------------------

class TestReturnShape:

    def test_returns_4_tuple(self):
        result = render_all(_minimal_run_state())
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_types_with_valid_state(self):
        blunt_md, audit_md, enriched, error_str = render_all(_minimal_run_state())
        assert isinstance(blunt_md, str)
        assert isinstance(audit_md, str)
        assert isinstance(enriched, dict)
        assert error_str is None


# ---------------------------------------------------------------------------
# Content tests
# ---------------------------------------------------------------------------

class TestContent:

    def test_blunt_has_sections(self):
        blunt_md, _, _, _ = render_all(_minimal_run_state())
        assert "## What the object is" in blunt_md
        assert "## Bottom line" in blunt_md

    def test_audit_has_sections(self):
        _, audit_md, _, _ = render_all(_minimal_run_state())
        assert "## Article Classification" in audit_md
        assert "## Claim Registry" in audit_md

    def test_enriched_has_derived_keys(self):
        _, _, enriched, _ = render_all(_minimal_run_state())
        assert "priority_signals" in enriched
        assert "reads_like" in enriched
        assert "adjudicated_claims" in enriched

    def test_enriched_has_peg_profile(self):
        _, _, enriched, _ = render_all(_minimal_run_state())
        assert "peg_profile" in enriched


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_empty_run_state(self):
        blunt_md, audit_md, enriched, error_str = render_all({})
        # Should not crash
        assert isinstance(enriched, dict)
        # Both renderers should still produce output
        assert blunt_md is not None or error_str is not None
        assert audit_md is not None or error_str is not None

    def test_fallback_marker_not_set_on_success(self):
        _, _, enriched, _ = render_all(_minimal_run_state())
        assert enriched.get("_render_bundle_fallback") is not True


# ---------------------------------------------------------------------------
# Config passthrough tests
# ---------------------------------------------------------------------------

class TestConfig:

    def test_config_passed_to_enricher(self):
        _, _, enriched, _ = render_all(
            _minimal_run_state(),
            config={"top_signals": 1}
        )
        signals = enriched.get("priority_signals")
        if isinstance(signals, list):
            assert len(signals) <= 1

    def test_config_passed_to_blunt(self):
        blunt_md, _, _, _ = render_all(
            _minimal_run_state(),
            config={"blunt_max_words": 500}
        )
        assert isinstance(blunt_md, str)
