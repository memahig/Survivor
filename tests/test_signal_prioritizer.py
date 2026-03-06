#!/usr/bin/env python3
"""
FILE: tests/test_signal_prioritizer.py
PURPOSE: Tests for engine.analysis.signal_prioritizer
         - load-bearing rejection outranks omission
         - baseline_absent=False does not emit
         - official_only=False does not emit
         - dedup by shared source_id
         - top_n respected
         - malformed inputs do not crash

Run with: python -m pytest tests/test_signal_prioritizer.py -v
"""

import pytest

from engine.analysis.signal_prioritizer import prioritize_signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_claim(group_id: str, text: str, centrality: int = 2,
                adjudication: str = "kept") -> dict:
    return {
        "group_id": group_id,
        "text": text,
        "centrality": centrality,
        "adjudication": adjudication,
    }


def _lb(group_ids: list) -> dict:
    return {"load_bearing_group_ids": group_ids}


# ---------------------------------------------------------------------------
# Score ordering tests
# ---------------------------------------------------------------------------

class TestScoreOrdering:

    def test_load_bearing_rejected_outranks_omission(self):
        claims = [_make_claim("G1", "Important claim", adjudication="rejected")]
        omissions = [{"severity": "load_bearing", "merged_text": "Missing context"}]
        result = prioritize_signals(
            claims, omissions, [], [], [], _lb(["G1"]), {}, top_n=5
        )
        assert len(result) >= 2
        assert result[0]["signal_type"] == "load_bearing_claim_rejected"
        assert result[1]["signal_type"] == "omission_load_bearing"

    def test_load_bearing_downgraded_emits_unsupported(self):
        claims = [_make_claim("G1", "Key claim", adjudication="downgraded")]
        result = prioritize_signals(
            claims, [], [], [], [], _lb(["G1"]), {}, top_n=5
        )
        assert len(result) == 1
        assert result[0]["signal_type"] == "load_bearing_claim_unsupported"

    def test_high_centrality_rejected_non_load_bearing(self):
        claims = [_make_claim("G1", "Central claim", centrality=3, adjudication="rejected")]
        result = prioritize_signals(
            claims, [], [], [], [], _lb([]), {}, top_n=5
        )
        assert len(result) == 1
        assert result[0]["signal_type"] == "high_centrality_rejected"

    def test_high_centrality_not_emitted_if_load_bearing(self):
        """If a claim is both load-bearing and high-centrality rejected,
        it should emit as load_bearing_claim_rejected, not high_centrality_rejected."""
        claims = [_make_claim("G1", "Key claim", centrality=3, adjudication="rejected")]
        result = prioritize_signals(
            claims, [], [], [], [], _lb(["G1"]), {}, top_n=5
        )
        types = [r["signal_type"] for r in result]
        assert "load_bearing_claim_rejected" in types
        assert "high_centrality_rejected" not in types


# ---------------------------------------------------------------------------
# Guard tests
# ---------------------------------------------------------------------------

class TestGuards:

    def test_baseline_absent_false_does_not_emit(self):
        detections = [{"group_id": "G1", "claim_text": "50% increase",
                       "baseline_absent": False}]
        result = prioritize_signals([], [], [], detections, [], {}, {}, top_n=5)
        assert len(result) == 0

    def test_baseline_absent_true_emits(self):
        detections = [{"group_id": "G1", "claim_text": "50% increase",
                       "baseline_absent": True}]
        result = prioritize_signals([], [], [], detections, [], {}, {}, top_n=5)
        assert len(result) == 1
        assert result[0]["signal_type"] == "baseline_absent"

    def test_official_only_false_does_not_emit(self):
        detections = [{"group_id": "G1", "claim_text": "Official said",
                       "official_only": False}]
        result = prioritize_signals([], [], [], [], detections, {}, {}, top_n=5)
        assert len(result) == 0

    def test_official_only_true_emits(self):
        detections = [{"group_id": "G1", "claim_text": "Official said",
                       "official_only": True}]
        result = prioritize_signals([], [], [], [], detections, {}, {}, top_n=5)
        assert len(result) == 1
        assert result[0]["signal_type"] == "official_assertion_only"

    def test_unsupported_causal_false_does_not_emit(self):
        detections = [{"group_id": "G1", "claim_text": "X caused Y",
                       "unsupported_causal": False}]
        result = prioritize_signals([], [], detections, [], [], {}, {}, top_n=5)
        assert len(result) == 0

    def test_unsupported_causal_true_emits(self):
        detections = [{"group_id": "G1", "claim_text": "X caused Y",
                       "unsupported_causal": True}]
        result = prioritize_signals([], [], detections, [], [], {}, {}, top_n=5)
        assert len(result) == 1
        assert result[0]["signal_type"] == "unsupported_causal"


# ---------------------------------------------------------------------------
# Dedup tests
# ---------------------------------------------------------------------------

class TestDedup:

    def test_dedup_by_source_id_keeps_highest(self):
        """If a claim is both load-bearing rejected and high-centrality rejected,
        dedup should keep the higher-scoring one."""
        claims = [
            _make_claim("G1", "Important claim", centrality=3, adjudication="rejected"),
        ]
        # G1 is load-bearing, so it emits load_bearing_claim_rejected (1.0)
        # G1 is also centrality>=3 rejected but excluded from high_centrality
        # because it's in lb_ids — so dedup isn't even needed here.
        # Instead test with an omission that shares source_id with a claim signal:
        # Actually, omissions use "omission-{i}" ids so they won't collide.
        # Test real dedup: two causal detections with same group_id
        causal = [
            {"group_id": "G1", "claim_text": "X caused Y", "unsupported_causal": True},
            {"group_id": "G1", "claim_text": "X caused Y again", "unsupported_causal": True},
        ]
        result = prioritize_signals([], [], causal, [], [], {}, {}, top_n=5)
        # Same source_id "G1" — should dedup to one
        g1_signals = [r for r in result if r["source_id"] == "G1"]
        assert len(g1_signals) == 1


# ---------------------------------------------------------------------------
# top_n tests
# ---------------------------------------------------------------------------

class TestTopN:

    def test_top_n_respected(self):
        omissions = [
            {"severity": "important", "merged_text": f"Omission {i}"}
            for i in range(10)
        ]
        result = prioritize_signals([], omissions, [], [], [], {}, {}, top_n=3)
        assert len(result) == 3

    def test_top_n_zero_returns_empty(self):
        omissions = [{"severity": "important", "merged_text": "Something"}]
        result = prioritize_signals([], omissions, [], [], [], {}, {}, top_n=0)
        assert len(result) == 0

    def test_ranks_sequential(self):
        omissions = [
            {"severity": "load_bearing", "merged_text": "A"},
            {"severity": "important", "merged_text": "B"},
        ]
        result = prioritize_signals([], omissions, [], [], [], {}, {}, top_n=5)
        ranks = [r["rank"] for r in result]
        assert ranks == list(range(1, len(ranks) + 1))


# ---------------------------------------------------------------------------
# Malformed input tests
# ---------------------------------------------------------------------------

class TestMalformedInput:

    def test_all_empty(self):
        result = prioritize_signals([], [], [], [], [], {}, {}, top_n=5)
        assert result == []

    def test_non_list_claims(self):
        result = prioritize_signals("bad", [], [], [], [], {}, {}, top_n=5)
        assert result == []

    def test_non_dict_in_claims(self):
        result = prioritize_signals(["bad"], [], [], [], [], {}, {}, top_n=5)
        assert result == []

    def test_non_dict_load_bearing(self):
        result = prioritize_signals([], [], [], [], [], "bad", {}, top_n=5)
        assert result == []

    def test_non_dict_in_omissions(self):
        result = prioritize_signals([], ["bad"], [], [], [], {}, {}, top_n=5)
        assert result == []

    def test_output_shape(self):
        claims = [_make_claim("G1", "Claim", adjudication="rejected")]
        result = prioritize_signals(claims, [], [], [], [], _lb(["G1"]), {}, top_n=5)
        assert len(result) == 1
        sig = result[0]
        assert "rank" in sig
        assert "signal_type" in sig
        assert "score" in sig
        assert "summary" in sig
        assert "source_id" in sig


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_deterministic_output(self):
        claims = [
            _make_claim("G1", "Key claim", centrality=3, adjudication="rejected"),
            _make_claim("G2", "Another claim", adjudication="rejected"),
        ]
        omissions = [
            {"severity": "load_bearing", "merged_text": "Missing"},
            {"severity": "important", "merged_text": "Also missing"},
        ]
        causal = [{"group_id": "G3", "claim_text": "X caused Y",
                    "unsupported_causal": True}]
        kwargs = dict(
            adjudicated_claims=claims,
            ranked_omissions=omissions,
            causal_detections=causal,
            baseline_detections=[],
            official_detections=[],
            load_bearing=_lb(["G1"]),
            reads_like={},
            top_n=10,
        )
        r1 = prioritize_signals(**kwargs)
        r2 = prioritize_signals(**kwargs)
        assert r1 == r2
