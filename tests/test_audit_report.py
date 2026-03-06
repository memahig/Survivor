#!/usr/bin/env python3
"""
FILE: tests/test_audit_report.py
PURPOSE: Tests for engine.render.audit_report
         - all 14 section headers present
         - missing data → "Not assessed" (fail-closed)
         - no word limit enforced
         - section-level error isolation

Run with: python -m pytest tests/test_audit_report.py -v
"""

import pytest

from engine.render.audit_report import render_audit_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_enriched() -> dict:
    """Build a reasonably complete enriched substrate for audit testing."""
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
                "counterfactual_requirements": [{"text": "Need independent data"}],
            },
            "gemini": {
                "whole_article_judgment": {"classification": "analysis", "confidence": "medium"},
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
                            "reviewer_votes": {
                                "openai": {"vote": "supported", "confidence": "high"},
                                "gemini": {"vote": "supported", "confidence": "medium"},
                            },
                        },
                    ]
                }
            },
            "article_track": {
                "adjudicated_whole_article_judgment": {
                    "classification": "reporting",
                    "confidence": "high",
                    "evidence_eids": ["E1"],
                    "tally": [{"classification": "reporting", "models": ["openai", "gemini"], "score": 2}],
                    "disagreements": [],
                }
            },
            "structural_forensics": {
                "argument_integrity": {
                    "merged_argument_fragility": "low",
                    "argument_fragility_by_reviewer": {"openai": "low", "gemini": "low"},
                    "load_bearing_claim_ids": ["C1"],
                    "weak_link_claim_ids": [],
                    "reason_by_reviewer": {"openai": "Solid structure", "gemini": "Well supported"},
                },
                "article_omissions": [],
                "framing_omissions": [],
                "claim_omissions": [],
                "rival_narratives": [
                    {
                        "lens": "Alternative economic view",
                        "merged_summary": "Growth may be overstated",
                        "structural_fragility": "medium",
                        "concern_level": "elevated",
                        "supporting_reviewers": ["gemini"],
                        "claims_weakened_if_true": ["G1"],
                    }
                ],
                "argument_summary": {
                    "by_reviewer": {
                        "openai": {
                            "main_conclusion": "Economy is growing",
                            "supporting_reasons": ["Official data supports this"],
                        },
                    },
                    "merged_rival_explanations_missing": ["Alternative metrics"],
                },
                "shared_blind_spot_check": {"status": "pass"},
            },
        },
        "gsae": {
            "settings": {"version": "1.0", "epsilon": 0.1, "tau": 0.05},
            "artifacts": [{"symmetry_status": "symmetric", "delta": 0.02}],
        },
        "divergence_radar": {
            "status": "run",
            "whole_article_conflict": False,
            "central_claim_instability": False,
            "unsupported_core_rate": 0.0,
            "undetermined_core_rate": 0.0,
            "gsae_quarantine_count": 0,
            "notes": [],
        },
        "verification": {"enabled": True, "note": "noop_verifier"},
        # Derived analysis keys
        "story_clusters": [
            {
                "cluster_id": "SC001",
                "member_group_ids": ["G1"],
                "canonical_text": "GDP grew by 3%",
                "max_centrality": 3,
                "adjudication_summary": {"kept": 1, "rejected": 0, "downgraded": 0},
            }
        ],
        "load_bearing": {
            "load_bearing_group_ids": ["G1"],
            "load_bearing_texts": ["GDP grew by 3%"],
            "weak_link_group_ids": [],
            "weak_link_texts": [],
            "argument_fragility": "low",
            "source": "argument_integrity+centrality",
        },
        "ranked_omissions": [],
        "causal_detections": [],
        "baseline_detections": [],
        "official_detections": [],
        "reads_like": {"label": "reporting", "flags": {}, "matched_rule": 6},
        "priority_signals": [],
    }


# ---------------------------------------------------------------------------
# Section header tests
# ---------------------------------------------------------------------------

class TestSectionHeaders:

    def test_all_14_headers_present(self):
        md = render_audit_report(_full_enriched())
        expected_headers = [
            "## Article Classification",
            "## Reviewer Comparison",
            "## Claim Registry",
            "## Story Clusters",
            "## Load-Bearing Analysis",
            "## Evidence Map",
            "## Verification",
            "## Omissions",
            "## Signal Detections",
            "## Rival Narratives",
            "## Argument Summary",
            "## Symmetry Analysis",
            "## Divergence Radar",
            "## Adjudication Summary",
        ]
        for header in expected_headers:
            assert header in md, f"Missing header: {header}"

    def test_report_title(self):
        md = render_audit_report(_full_enriched())
        assert "# Audit Report" in md

    def test_article_title_in_header(self):
        md = render_audit_report(_full_enriched())
        assert "Test Article" in md

    def test_source_url_in_header(self):
        md = render_audit_report(_full_enriched())
        assert "http://example.com" in md


# ---------------------------------------------------------------------------
# Content tests
# ---------------------------------------------------------------------------

class TestContent:

    def test_claim_registry_shows_claims(self):
        md = render_audit_report(_full_enriched())
        assert "G1" in md
        assert "GDP grew" in md

    def test_reviewer_table(self):
        md = render_audit_report(_full_enriched())
        assert "Openai" in md or "openai" in md
        assert "Gemini" in md or "gemini" in md

    def test_evidence_map_shows_items(self):
        md = render_audit_report(_full_enriched())
        assert "E1" in md
        assert "Evidence quote one" in md

    def test_rival_narratives_shown(self):
        md = render_audit_report(_full_enriched())
        assert "Alternative economic view" in md

    def test_divergence_radar_values(self):
        md = render_audit_report(_full_enriched())
        assert "Whole-article conflict" in md or "whole_article_conflict" in md

    def test_adjudication_summary_counts(self):
        md = render_audit_report(_full_enriched())
        assert "Kept" in md or "kept" in md

    def test_story_clusters_shown(self):
        md = render_audit_report(_full_enriched())
        assert "SC001" in md

    def test_load_bearing_section(self):
        md = render_audit_report(_full_enriched())
        assert "Load-Bearing" in md or "load-bearing" in md


# ---------------------------------------------------------------------------
# Fail-closed tests
# ---------------------------------------------------------------------------

class TestFailClosed:

    def test_empty_enriched(self):
        """Empty enriched should not crash, all sections should render."""
        md = render_audit_report({})
        assert "# Audit Report" in md
        # Should have at least some "Not assessed" or empty-data messages
        assert len(md) > 100

    def test_missing_adjudicated(self):
        enriched = _full_enriched()
        del enriched["adjudicated"]
        md = render_audit_report(enriched)
        assert "## Article Classification" in md

    def test_missing_phase2(self):
        enriched = _full_enriched()
        del enriched["phase2"]
        md = render_audit_report(enriched)
        assert "## Reviewer Comparison" in md
        assert "Not assessed" in md

    def test_error_in_story_clusters(self):
        enriched = _full_enriched()
        enriched["story_clusters"] = {"error": "module failed"}
        md = render_audit_report(enriched)
        assert "## Story Clusters" in md
        assert "module failed" in md

    def test_error_in_load_bearing(self):
        enriched = _full_enriched()
        enriched["load_bearing"] = {"error": "module failed"}
        md = render_audit_report(enriched)
        assert "## Load-Bearing Analysis" in md

    def test_section_exception_does_not_crash(self):
        """Even with deeply malformed data, the report should render."""
        enriched = {
            "adjudicated": "not a dict",
            "phase2": 42,
            "gsae": "invalid",
        }
        md = render_audit_report(enriched)
        assert "# Audit Report" in md


# ---------------------------------------------------------------------------
# No word limit test
# ---------------------------------------------------------------------------

class TestNoWordLimit:

    def test_long_claim_registry_not_truncated(self):
        """Audit report should not enforce word limits."""
        enriched = _full_enriched()
        # Add many claims
        claims = enriched["adjudicated"]["claim_track"]["arena"]["adjudicated_claims"]
        for i in range(50):
            claims.append({
                "group_id": f"G{i + 10}",
                "member_claim_ids": [f"C{i + 10}"],
                "text": f"Claim number {i + 10} about some detailed topic with context",
                "type": "factual",
                "centrality": 2,
                "claim_kind": "world_fact",
                "checkability": "checkable",
                "evidence_eids": [],
                "adjudication": "kept",
                "tally": {},
                "reviewer_votes": {},
            })
        md = render_audit_report(enriched)
        # All claims should appear
        assert "G50" in md


# ---------------------------------------------------------------------------
# Footer test
# ---------------------------------------------------------------------------

class TestFooter:

    def test_footer_present(self):
        md = render_audit_report(_full_enriched())
        assert "Generated by Survivor" in md
