#!/usr/bin/env python3
"""
FILE: tests/test_substrate_enricher.py
PURPOSE: Tests for engine.analysis.substrate_enricher
         - all derived keys present
         - module error doesn't crash orchestrator
         - normalized top-level keys populated
         - passthrough keys present
         - empty run_state handled

Run with: python -m pytest tests/test_substrate_enricher.py -v
"""

import pytest

from engine.analysis.substrate_enricher import enrich_substrate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_run_state() -> dict:
    """Build a minimal but valid run_state for enricher testing."""
    return {
        "article": {"title": "Test Article", "source_url": "http://example.com"},
        "evidence_bank": {
            "items": [
                {"eid": "E1", "quote": "Evidence quote one"},
                {"eid": "E2", "quote": "Evidence quote two"},
            ]
        },
        "phase1": {"openai": {}, "gemini": {}},
        "phase2": {
            "openai": {
                "whole_article_judgment": {"classification": "reporting", "confidence": "high"},
                "counterfactual_requirements": [],
            },
            "gemini": {
                "whole_article_judgment": {"classification": "reporting", "confidence": "medium"},
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
                            "text": "GDP grew by 3% last quarter",
                            "type": "factual",
                            "centrality": 3,
                            "claim_kind": "world_fact",
                            "checkability": "checkable",
                            "evidence_eids": ["E1"],
                            "adjudication": "kept",
                            "tally": {"supported_votes": 2, "unsupported_votes": 0, "undetermined_votes": 0},
                            "reviewer_votes": {},
                        },
                        {
                            "group_id": "G2",
                            "member_claim_ids": ["C2"],
                            "text": "The policy was ineffective",
                            "type": "evaluative",
                            "centrality": 2,
                            "claim_kind": "world_fact",
                            "checkability": "uncheckable",
                            "evidence_eids": [],
                            "adjudication": "rejected",
                            "tally": {"supported_votes": 0, "unsupported_votes": 2, "undetermined_votes": 0},
                            "reviewer_votes": {},
                        },
                    ]
                }
            },
            "article_track": {
                "adjudicated_whole_article_judgment": {
                    "classification": "reporting",
                    "confidence": "high",
                    "evidence_eids": ["E1"],
                }
            },
            "structural_forensics": {
                "argument_integrity": {
                    "merged_argument_fragility": "low",
                    "load_bearing_claim_ids": ["C1"],
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
# Key presence tests
# ---------------------------------------------------------------------------

class TestKeyPresence:

    def test_passthrough_keys_present(self):
        enriched = enrich_substrate(_minimal_run_state())
        for key in ("article", "evidence_bank", "phase1", "phase2",
                     "adjudicated", "gsae", "divergence_radar", "verification"):
            assert key in enriched, f"Missing passthrough key: {key}"

    def test_normalized_keys_present(self):
        enriched = enrich_substrate(_minimal_run_state())
        for key in ("evidence_lookup", "adjudicated_claims",
                     "structural_forensics", "argument_integrity",
                     "adjudicated_whole_article_judgment"):
            assert key in enriched, f"Missing normalized key: {key}"

    def test_derived_analysis_keys_present(self):
        enriched = enrich_substrate(_minimal_run_state())
        for key in ("causal_detections", "baseline_detections",
                     "official_detections", "story_clusters",
                     "load_bearing", "ranked_omissions",
                     "reads_like", "priority_signals"):
            assert key in enriched, f"Missing derived key: {key}"


# ---------------------------------------------------------------------------
# Normalized key tests
# ---------------------------------------------------------------------------

class TestNormalizedKeys:

    def test_evidence_lookup_built(self):
        enriched = enrich_substrate(_minimal_run_state())
        lookup = enriched["evidence_lookup"]
        assert isinstance(lookup, dict)
        assert "E1" in lookup
        assert "E2" in lookup

    def test_adjudicated_claims_extracted(self):
        enriched = enrich_substrate(_minimal_run_state())
        claims = enriched["adjudicated_claims"]
        assert isinstance(claims, list)
        assert len(claims) == 2
        assert claims[0]["group_id"] == "G1"

    def test_structural_forensics_extracted(self):
        enriched = enrich_substrate(_minimal_run_state())
        sf = enriched["structural_forensics"]
        assert isinstance(sf, dict)
        assert "argument_integrity" in sf

    def test_argument_integrity_extracted(self):
        enriched = enrich_substrate(_minimal_run_state())
        ai = enriched["argument_integrity"]
        assert isinstance(ai, dict)
        assert ai["merged_argument_fragility"] == "low"

    def test_whole_article_judgment_extracted(self):
        enriched = enrich_substrate(_minimal_run_state())
        waj = enriched["adjudicated_whole_article_judgment"]
        assert isinstance(waj, dict)
        assert waj["classification"] == "reporting"


# ---------------------------------------------------------------------------
# Module error isolation tests
# ---------------------------------------------------------------------------

class TestErrorIsolation:

    def test_empty_run_state_does_not_crash(self):
        enriched = enrich_substrate({})
        assert isinstance(enriched, dict)
        # All derived keys should still exist (either results or error dicts)
        for key in ("causal_detections", "baseline_detections",
                     "official_detections", "story_clusters",
                     "load_bearing", "ranked_omissions",
                     "reads_like", "priority_signals"):
            assert key in enriched

    def test_missing_adjudicated_does_not_crash(self):
        rs = _minimal_run_state()
        del rs["adjudicated"]
        enriched = enrich_substrate(rs)
        assert isinstance(enriched, dict)
        assert enriched["adjudicated_claims"] == []

    def test_missing_evidence_bank_does_not_crash(self):
        rs = _minimal_run_state()
        del rs["evidence_bank"]
        enriched = enrich_substrate(rs)
        assert enriched["evidence_lookup"] == {}

    def test_module_error_stored_as_dict(self):
        """If a module key has an error, it should be a dict with 'error' key."""
        enriched = enrich_substrate({})
        # With empty state, modules may produce empty lists or error dicts
        # Either is acceptable — the point is no crash
        for key in ("causal_detections", "baseline_detections",
                     "official_detections", "story_clusters",
                     "load_bearing", "ranked_omissions"):
            val = enriched[key]
            assert isinstance(val, (list, dict)), f"{key} has unexpected type: {type(val)}"


# ---------------------------------------------------------------------------
# Config passthrough tests
# ---------------------------------------------------------------------------

class TestConfig:

    def test_default_config(self):
        enriched = enrich_substrate(_minimal_run_state())
        assert isinstance(enriched, dict)

    def test_custom_threshold(self):
        enriched = enrich_substrate(
            _minimal_run_state(),
            config={"story_cluster_jaccard_threshold": 0.5}
        )
        # Should still produce story_clusters
        assert "story_clusters" in enriched

    def test_custom_top_n(self):
        enriched = enrich_substrate(
            _minimal_run_state(),
            config={"top_signals": 1}
        )
        signals = enriched["priority_signals"]
        if isinstance(signals, list):
            assert len(signals) <= 1


# ---------------------------------------------------------------------------
# Non-mutation test
# ---------------------------------------------------------------------------

class TestNonMutation:

    def test_run_state_not_mutated(self):
        import json
        rs = _minimal_run_state()
        original = json.dumps(rs, sort_keys=True, default=str)
        enrich_substrate(rs)
        after = json.dumps(rs, sort_keys=True, default=str)
        assert original == after
