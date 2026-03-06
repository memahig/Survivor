#!/usr/bin/env python3
"""
tests/test_judge_hardening.py
Adversarial hardening tests for engine/arena/judge.py v0.2

Coverage:
  JH1  — E1 collision with divergent text raises; same text ok; one-side None ok
  JH2  — E2 self-link raises
  JH3  — E3 dangling ref raises
  JH4  — E4 consensus paradox flags; shared-eid negative control
  JH5  — non-numeric model_weight raises; non-numeric conf_weight raises
  JH6  — W_score rounded to 6 dp (pins 1/3 = 0.333333)
  JH7  — status thresholds: kept / rejected / insufficient / downgraded
  JH8  — E4 negative-control: only 1 supporter -> no flag
  JH9  — output schema: required keys, sorted fields
  Extra — multi-group output sorted by group_id
  Extra — empty phase2 yields no groups
  Extra — non-dict pack silently skipped
  Extra — flags key absent when empty
"""

import pytest

from engine.arena.judge import adjudicate


BASE_CONFIG = {
    "confidence_weights": {"high": 1.5, "medium": 1.0, "low": 0.5},
    "model_weights": {},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _one_claim(claim_id, text=None, eids=None):
    """Build a minimal claim dict."""
    c: dict = {"claim_id": claim_id}
    if text is not None:
        c["text"] = text
    if eids:
        c["evidence_eids"] = eids
    return c


def _vote(claim_id, vote="supported", conf="medium", nd=None):
    """Build a cross_claim_vote dict."""
    v: dict = {"claim_id": claim_id, "vote": vote, "confidence": conf}
    if nd:
        v["near_duplicate_of"] = nd
    return v


def _pack(claims=None, votes=None):
    """Build a phase2 reviewer pack."""
    cl = claims or []
    return {
        "pillar_claims": [],
        "questionable_claims": cl,
        "background_claims_summary": {"total_claims_estimate": len(cl), "not_triaged_count": 0},
        "cross_claim_votes": votes or [],
    }


# ---------------------------------------------------------------------------
# JH1: E1 — collision with divergent text
# ---------------------------------------------------------------------------


def test_jh1_collision_divergent_text_raises():
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1", text="the sky is blue")]),
            "r2": _pack([_one_claim("c1", text="the sky is red")]),
        }
    }
    with pytest.raises(RuntimeError, match="Claim ID collision"):
        adjudicate(run, BASE_CONFIG)


def test_jh1_collision_same_text_ok():
    """Same text from two reviewers: no collision."""
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1", text="identical")], [_vote("c1")]),
            "r2": _pack([_one_claim("c1", text="identical")], [_vote("c1")]),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    assert len(result["adjudicated_claims"]) == 1


def test_jh1_collision_one_side_none_text_ok():
    """One side has no text -> not divergent (None is not a mismatch)."""
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1", text=None)], [_vote("c1")]),
            "r2": _pack([_one_claim("c1", text="some text")], [_vote("c1")]),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    assert len(result["adjudicated_claims"]) == 1


# ---------------------------------------------------------------------------
# JH2: E2 — self-link raises
# ---------------------------------------------------------------------------


def test_jh2_self_link_raises():
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c1")],
                [_vote("c1", "supported", nd=["c1"])],
            )
        }
    }
    with pytest.raises(RuntimeError, match="Self-link"):
        adjudicate(run, BASE_CONFIG)


# ---------------------------------------------------------------------------
# JH3: E3 — dangling reference raises
# ---------------------------------------------------------------------------


def test_jh3_dangling_ref_raises():
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c1")],
                [_vote("c1", "supported", nd=["c_unknown"])],
            )
        }
    }
    with pytest.raises(RuntimeError, match="dangling reference"):
        adjudicate(run, BASE_CONFIG)


# ---------------------------------------------------------------------------
# JH4: E4 — consensus paradox appends flag (non-fatal)
# ---------------------------------------------------------------------------


def test_jh4_consensus_paradox_flags():
    """Two reviewers both 'supported' on same claim with zero overlapping eids -> flag."""
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c1", eids=["e1"])],
                [_vote("c1", "supported")],
            ),
            "r2": _pack(
                [_one_claim("c1", eids=["e2"])],
                [_vote("c1", "supported")],
            ),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert "high_structural_risk" in grp.get("flags", [])


def test_jh4_no_paradox_when_eids_overlap():
    """Shared eid between two 'supported' reviewers -> no E4 flag."""
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c1", eids=["e1", "e2"])],
                [_vote("c1", "supported")],
            ),
            "r2": _pack(
                [_one_claim("c1", eids=["e2", "e3"])],
                [_vote("c1", "supported")],
            ),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert "high_structural_risk" not in grp.get("flags", [])


# ---------------------------------------------------------------------------
# JH5: Non-numeric weights raise RuntimeError
# ---------------------------------------------------------------------------


def test_jh5_non_numeric_model_weight_raises():
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], [_vote("c1")]),
        }
    }
    cfg = {
        "confidence_weights": {"high": 1.5, "medium": 1.0, "low": 0.5},
        "model_weights": {"r1": "bad"},
    }
    with pytest.raises(RuntimeError, match="is not numeric"):
        adjudicate(run, cfg)


def test_jh5_non_numeric_conf_weight_raises():
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], [_vote("c1", conf="high")]),
        }
    }
    cfg = {
        "confidence_weights": {"high": "bad", "medium": 1.0, "low": 0.5},
        "model_weights": {},
    }
    with pytest.raises(RuntimeError, match="is not numeric"):
        adjudicate(run, cfg)


# ---------------------------------------------------------------------------
# JH6: W_score rounded to 6 decimal places
# ---------------------------------------------------------------------------


def test_jh6_wscore_rounded_to_6dp():
    """
    r1 votes 'supported', r2 and r3 vote 'undetermined'.
    All model_weight=1.0 (default), conf=medium (weight=1.0).
    W = 1.0 / 3.0 = 0.333333... -> round(1/3, 6) = 0.333333
    """
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], [_vote("c1", "supported")]),
            "r2": _pack([_one_claim("c1")], [_vote("c1", "undetermined")]),
            "r3": _pack([_one_claim("c1")], [_vote("c1", "undetermined")]),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert grp["wscore"] == round(1 / 3, 6)


# ---------------------------------------------------------------------------
# JH7: Status thresholds
# ---------------------------------------------------------------------------


def test_jh7_status_kept():
    """W >= 0.6 -> 'kept'. High-conf support gives W=1.0."""
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], [_vote("c1", "supported", "high")]),
        }
    }
    cfg = {
        "confidence_weights": {"high": 1.5, "medium": 1.0, "low": 0.5},
        "model_weights": {},
    }
    result = adjudicate(run, cfg)
    grp = result["adjudicated_claims"][0]
    assert grp["status"] == "kept"
    assert grp["wscore"] >= 0.6


def test_jh7_status_rejected():
    """W <= -0.6 -> 'rejected'. High-conf unsupported gives W=-1.0."""
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], [_vote("c1", "unsupported", "high")]),
        }
    }
    cfg = {
        "confidence_weights": {"high": 1.5, "medium": 1.0, "low": 0.5},
        "model_weights": {},
    }
    result = adjudicate(run, cfg)
    grp = result["adjudicated_claims"][0]
    assert grp["status"] == "rejected"
    assert grp["wscore"] <= -0.6


def test_jh7_status_insufficient():
    """No cross_claim_votes -> total_weight=0 -> W=0.0 -> 'insufficient'."""
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], []),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert grp["status"] == "insufficient"
    assert grp["wscore"] == 0.0


def test_jh7_status_downgraded():
    """0.2 <= |W| < 0.6 -> 'downgraded'.
    r1 supported-low, r2+r3 unsupported-low: W = (0.5 - 0.5 - 0.5) / 1.5 = -0.333...
    """
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], [_vote("c1", "supported", "low")]),
            "r2": _pack([_one_claim("c1")], [_vote("c1", "unsupported", "low")]),
            "r3": _pack([_one_claim("c1")], [_vote("c1", "unsupported", "low")]),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert grp["status"] == "downgraded"


# ---------------------------------------------------------------------------
# JH8: E4 negative-control — only 1 reviewer 'supported' -> no flag
# ---------------------------------------------------------------------------


def test_jh8_two_reviewers_only_one_supported_no_flag():
    """r1 votes 'supported', r2 votes 'undetermined'.
    E4 needs >=2 supporters; only 1 here -> no high_structural_risk flag."""
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c1", eids=["e1"])],
                [_vote("c1", "supported")],
            ),
            "r2": _pack(
                [_one_claim("c1", eids=["e2"])],
                [_vote("c1", "undetermined")],
            ),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert "high_structural_risk" not in grp.get("flags", [])


# ---------------------------------------------------------------------------
# JH9: Output schema invariants
# ---------------------------------------------------------------------------


def test_jh9_required_schema_keys_present():
    """Every adjudicated group must have all required output keys."""
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c1", text="hello", eids=["e1"])],
                [_vote("c1", "supported")],
            ),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    assert "adjudicated_claims" in result
    grp = result["adjudicated_claims"][0]
    for key in (
        "group_id",
        "member_claim_ids",
        "canonical_text",
        "status",
        "wscore",
        "evidence_union",
        "contributing_reviewers",
    ):
        assert key in grp, f"Missing required key: {key!r}"


def test_jh9_contributing_reviewers_sorted():
    """contributing_reviewers must be lexicographically sorted."""
    run = {
        "phase2": {
            "r_z": _pack([_one_claim("c1")], [_vote("c1")]),
            "r_a": _pack([_one_claim("c1")], [_vote("c1")]),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert grp["contributing_reviewers"] == sorted(grp["contributing_reviewers"])


def test_jh9_evidence_union_sorted():
    """evidence_union must be lexicographically sorted."""
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c1", eids=["z_eid", "a_eid"])],
                [_vote("c1")],
            ),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert grp["evidence_union"] == sorted(grp["evidence_union"])


def test_jh9_member_claim_ids_sorted():
    """member_claim_ids must be lexicographically sorted."""
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("c_z"), _one_claim("c_a")],
                [
                    _vote("c_z", "supported", nd=["c_a"]),
                    _vote("c_a", "supported"),
                ],
            )
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert grp["member_claim_ids"] == sorted(grp["member_claim_ids"])


# ---------------------------------------------------------------------------
# Extra: multi-group output sorted by group_id
# ---------------------------------------------------------------------------


def test_jh_multi_group_output_sorted_by_group_id():
    """Two singletons 'b1' and 'a1' — output must be sorted ['a1', 'b1']."""
    run = {
        "phase2": {
            "r1": _pack(
                [_one_claim("b1"), _one_claim("a1")],
                [_vote("b1", "supported"), _vote("a1", "supported")],
            )
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    group_ids = [g["group_id"] for g in result["adjudicated_claims"]]
    assert group_ids == sorted(group_ids)
    assert group_ids == ["a1", "b1"]


# ---------------------------------------------------------------------------
# Extra: edge cases
# ---------------------------------------------------------------------------


def test_jh_empty_phase2_yields_no_groups():
    result = adjudicate({"phase2": {}}, BASE_CONFIG)
    assert result["adjudicated_claims"] == []


def test_jh_non_dict_pack_silently_skipped():
    """Non-dict reviewer pack is skipped; other packs still processed."""
    run = {
        "phase2": {
            "r_bad": "not-a-dict",
            "r1": _pack([_one_claim("c1")], [_vote("c1", "supported")]),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    assert len(result["adjudicated_claims"]) == 1


def test_jh_flags_key_absent_when_no_flags_triggered():
    """flags key must be absent (not an empty list) when no E4 triggered."""
    run = {
        "phase2": {
            "r1": _pack([_one_claim("c1")], [_vote("c1", "supported")]),
        }
    }
    result = adjudicate(run, BASE_CONFIG)
    grp = result["adjudicated_claims"][0]
    assert "flags" not in grp


def test_jh_confidence_none_weight_value_strict():
    """
    Verify explicit None confidence behaves as weight 1.0 (default fallback),
    distinguishable from 'medium' if we set medium != 1.0.
    r1: supported, confidence=None -> defaults to 1.0
    r2: unsupported, confidence=medium -> weight 0.5
    W = (1.0*1 + 0.5*-1) / (1.0 + 0.5) = 0.5/1.5 = 0.333333...
    If None had defaulted to medium (0.5), score would be 0.0.
    """
    config = {
        "confidence_weights": {"medium": 0.5},
        "model_weights": {"r1": 1.0, "r2": 1.0},
    }
    phase2 = {
        "r1": _pack([_one_claim("c1")], [_vote("c1", "supported", conf=None)]),
        "r2": _pack([], [_vote("c1", "unsupported", conf="medium")]),
    }
    result = adjudicate({"phase2": phase2}, config)
    wscore = result["adjudicated_claims"][0]["wscore"]
    assert wscore == round(1 / 3, 6)
