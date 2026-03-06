#!/usr/bin/env python3
"""
Tests for Plain Language Synthesis section in the Blunt Report renderer.
"""

import pytest
from engine.render.blunt_biaslens import (
    _compute_conflict_counts,
    _render_plain_language_synthesis,
    _reviewer_conclusion_sentence,
    _top_counterfactuals,
    render_blunt_biaslens,
    render_blunt_biaslens_json,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal run_state components
# ---------------------------------------------------------------------------

def _make_waj(cls="reporting", conf="high", eids=None):
    return {
        "classification": cls,
        "confidence": conf,
        "evidence_eids": eids or ["E1"],
    }


def _make_claim(claim_id, text, ctype="factual", centrality=2, eids=None):
    return {
        "claim_id": claim_id,
        "text": text,
        "type": ctype,
        "centrality": centrality,
        "evidence_eids": eids or ["E1"],
    }


def _make_cf(target, description, why, confidence="high"):
    return {
        "target_claim_id": target,
        "counterfactual_type": "source_reliability",
        "measurable_type": "attribution_check",
        "description": description,
        "why_it_changes_confidence": why,
        "confidence": confidence,
    }


def _make_group(gid, members, text, votes, adjudication="kept"):
    """Build an adjudicated claim group with tally computed from votes."""
    reviewer_votes = {}
    s_count, u_count, d_count = 0, 0, 0
    for reviewer, vote, conf in votes:
        reviewer_votes[reviewer] = {"vote": vote, "confidence": conf}
        if vote == "supported":
            s_count += 1
        elif vote == "unsupported":
            u_count += 1
        else:
            d_count += 1
    return {
        "group_id": gid,
        "member_claim_ids": members,
        "text": text,
        "type": "factual",
        "centrality": 2,
        "evidence_eids": ["E1"],
        "reviewer_votes": reviewer_votes,
        "tally": {
            "supported_score": s_count * 3.0,
            "unsupported_score": u_count * 3.0,
            "supported_votes": s_count,
            "unsupported_votes": u_count,
            "undetermined_votes": d_count,
        },
        "adjudication": adjudication,
    }


def _make_phase2(reviewers_config):
    """
    reviewers_config: list of (name, classification, confidence, claims, cfs)
    """
    phase2 = {}
    for name, cls, conf, claims, cfs in reviewers_config:
        phase2[name] = {
            "reviewer": name,
            "whole_article_judgment": _make_waj(cls, conf),
            "pillar_claims": [],
            "questionable_claims": claims,
            "background_claims_summary": {"total_claims_estimate": len(claims), "not_triaged_count": 0},
            "counterfactual_requirements": cfs,
            "cross_claim_votes": [],
            "omission_candidates": [],
            "main_conclusion": {},
            "scope_markers": [],
            "causal_links": [],
            "article_patterns": [],
            "evidence_density": {"claims_count": len(claims), "claims_with_internal_support": 0, "external_sources_count": 0},
            "claim_tickets": [],
            "article_tickets": [],
        }
    return phase2


def _make_adjudicated(classification, confidence, groups):
    return {
        "article_track": {
            "adjudicated_whole_article_judgment": {
                "classification": classification,
                "confidence": confidence,
                "evidence_eids": ["E1"],
                "tally": [(classification, 9.0)],
                "disagreements": [],
            },
            "whole_article_judgments": {},
            "article_tickets_by_model": {},
            "article_patterns_by_model": {},
            "counterfactual_requirements_by_model": {},
        },
        "claim_track": {
            "claims_by_model": {},
            "cross_claim_votes_by_model": {},
            "claim_tickets_by_model": {},
            "arena": {
                "adjudicated_claims": groups,
                "groups_count": len(groups),
                "edges": [],
            },
        },
        "consistency_checks": {},
        "final_tickets": [],
    }


def _make_run_state(phase2, adjudicated, gsae=None):
    return {
        "article": {"id": "A-test", "title": "Test Article", "source_url": "https://example.com"},
        "evidence_bank": {
            "items": [{"eid": "E1", "text": "Test evidence quote.", "quote": "Test evidence quote.", "locator": {"char_start": 0, "char_end": 20}, "source_id": "S1"}],
            "used_chars": 20,
        },
        "phase2": phase2,
        "adjudicated": adjudicated,
        "gsae": gsae,
        "divergence_radar": {"status": "run", "whole_article_conflict": "low", "central_claim_instability": "low", "unsupported_core_rate": 0.0, "undetermined_core_rate": 0.0, "gsae_quarantine_count": 0, "notes": []},
    }


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestReviewerConclusionSentence:
    def test_high_confidence(self):
        s = _reviewer_conclusion_sentence("claude", "reporting", "high")
        assert s == "**Claude** sees this as **reporting**."

    def test_medium_confidence(self):
        s = _reviewer_conclusion_sentence("gemini", "analysis", "medium")
        assert "moderate confidence" in s

    def test_low_confidence(self):
        s = _reviewer_conclusion_sentence("openai", "advocacy", "low")
        assert "leans toward" in s


class TestTopCounterfactuals:
    def test_picks_highest_confidence(self):
        cfs = [
            _make_cf("c1", "desc1", "low conf reason", "low"),
            _make_cf("c2", "desc2", "high conf reason", "high"),
        ]
        result = _top_counterfactuals(cfs, {}, n=1)
        assert len(result) == 1
        assert "high conf reason" in result[0]

    def test_empty_returns_empty(self):
        assert _top_counterfactuals([], {}, n=1) == []


class TestComputeConflictCounts:
    def test_all_consensus(self):
        groups = [
            _make_group("G1", ["c1"], "claim1", [("a", "supported", "high"), ("b", "supported", "high")]),
            _make_group("G2", ["c2"], "claim2", [("a", "supported", "high"), ("b", "supported", "high")]),
        ]
        cc = _compute_conflict_counts(groups)
        assert cc["total_consensus"] == 2
        assert cc["minor"] == 0
        assert cc["moderate"] == 0
        assert cc["high"] == 0


# ---------------------------------------------------------------------------
# Synthesis block tests
# ---------------------------------------------------------------------------

class TestPlainLanguageSynthesis:
    def _standard_setup(self, cls_list=None, cfs_config=None):
        """Build a standard 3-reviewer run state."""
        cls_list = cls_list or [("claude", "reporting", "medium"), ("gemini", "reporting", "high"), ("openai", "reporting", "high")]
        cfs_config = cfs_config or {}

        reviewers = []
        for name, cls, conf in cls_list:
            claims = [_make_claim(f"{name}-C1", f"Claim by {name}")]
            cfs = cfs_config.get(name, [])
            reviewers.append((name, cls, conf, claims, cfs))

        phase2 = _make_phase2(reviewers)
        groups = [
            _make_group("G1", ["claude-C1", "gemini-C1", "openai-C1"], "Main claim",
                        [("claude", "supported", "high"), ("gemini", "supported", "high"), ("openai", "supported", "high")]),
        ]
        adjudicated = _make_adjudicated("reporting", "high", groups)
        return phase2, adjudicated, groups

    def test_all_agree_classification(self):
        phase2, adjudicated, groups = self._standard_setup()
        cc = _compute_conflict_counts(groups)
        result = _render_plain_language_synthesis(
            phase2, adjudicated, groups, cc, None, {}, {},
        )
        assert "All 3 reviewers classify this as **reporting**" in result

    def test_reviewers_disagree_classification(self):
        phase2, adjudicated, groups = self._standard_setup(
            cls_list=[("claude", "reporting", "high"), ("gemini", "analysis", "high"), ("openai", "reporting", "high")]
        )
        cc = _compute_conflict_counts(groups)
        result = _render_plain_language_synthesis(
            phase2, adjudicated, groups, cc, None, {}, {},
        )
        assert "split" in result.lower()

    def test_counterfactuals_produce_caution(self):
        cfs = {
            "claude": [_make_cf("claude-C1", "Qatar claim unverified", "Source is self-reported only", "high")],
        }
        phase2, adjudicated, groups = self._standard_setup(cfs_config=cfs)
        cc = _compute_conflict_counts(groups)
        claim_index = {"claude-C1": {"text": "Claim by claude", "centrality": 2, "type": "factual", "reviewer": "claude"}}
        result = _render_plain_language_synthesis(
            phase2, adjudicated, groups, cc, None, claim_index, {},
        )
        assert "verification concern" in result.lower()
        assert "Claude" in result

    def test_no_counterfactuals(self):
        phase2, adjudicated, groups = self._standard_setup()
        cc = _compute_conflict_counts(groups)
        result = _render_plain_language_synthesis(
            phase2, adjudicated, groups, cc, None, {}, {},
        )
        assert "No reviewers flagged specific verification gaps" in result

    def test_synthesis_paragraph(self):
        phase2, adjudicated, groups = self._standard_setup()
        cc = _compute_conflict_counts(groups)
        result = _render_plain_language_synthesis(
            phase2, adjudicated, groups, cc, None, {}, {},
        )
        assert "Survivor grouped" in result
        assert "total consensus" in result.lower()
        assert "Conclusion:" in result


# ---------------------------------------------------------------------------
# Integration: section placement in full render
# ---------------------------------------------------------------------------

class TestFullRenderIntegration:
    def test_section_appears_between_what_this_is_and_extractive(self):
        cls_list = [("claude", "reporting", "high"), ("gemini", "reporting", "high"), ("openai", "reporting", "high")]
        reviewers = []
        for name, cls, conf in cls_list:
            reviewers.append((name, cls, conf, [_make_claim(f"{name}-C1", f"Claim by {name}")], []))
        phase2 = _make_phase2(reviewers)
        groups = [
            _make_group("G1", ["claude-C1", "gemini-C1", "openai-C1"], "Main claim",
                        [("claude", "supported", "high"), ("gemini", "supported", "high"), ("openai", "supported", "high")]),
        ]
        adjudicated = _make_adjudicated("reporting", "high", groups)
        run_state = _make_run_state(phase2, adjudicated)

        md = render_blunt_biaslens(run_state, {})

        # Section order: "What this is" < "What the reviewers found" < "Extractive summary"
        idx_what = md.index("## What this is")
        idx_found = md.index("## What the reviewers found")
        idx_extract = md.index("## Extractive summary")
        assert idx_what < idx_found < idx_extract

    def test_json_output_has_plain_language_key(self):
        cls_list = [("claude", "reporting", "high"), ("gemini", "reporting", "high")]
        reviewers = []
        for name, cls, conf in cls_list:
            reviewers.append((name, cls, conf, [_make_claim(f"{name}-C1", f"Claim by {name}")], []))
        phase2 = _make_phase2(reviewers)
        groups = [
            _make_group("G1", ["claude-C1", "gemini-C1"], "Main claim",
                        [("claude", "supported", "high"), ("gemini", "supported", "high")]),
        ]
        adjudicated = _make_adjudicated("reporting", "high", groups)
        run_state = _make_run_state(phase2, adjudicated)

        result = render_blunt_biaslens_json(run_state, {})
        assert "plain_language_synthesis" in result
        pls = result["plain_language_synthesis"]
        assert pls["agreement"]["classification_unanimous"] is True
        assert pls["agreement"]["total_consensus_groups"] == 1
        assert pls["synthesis"]["total_groups"] == 1
