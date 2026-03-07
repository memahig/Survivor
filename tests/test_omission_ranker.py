#!/usr/bin/env python3
"""Tests for engine.analysis.omission_ranker — severity classification."""

import pytest

from engine.analysis.omission_ranker import rank_omissions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sf(**overrides):
    """Minimal structural_forensics dict."""
    base = {
        "article_omissions": [],
        "framing_omissions": [],
        "claim_omissions": [],
    }
    base.update(overrides)
    return base


def _claim(group_id, centrality=2, member_ids=None):
    return {
        "group_id": group_id,
        "centrality": centrality,
        "member_claim_ids": member_ids or [f"{group_id}-m1"],
    }


def _omission(kind_key, merged_text, concern_level="low", **extra):
    """Build a single omission entry for inclusion in structural_forensics."""
    om = {
        "missing_frame": merged_text,
        "merged_text": merged_text,
        "concern_level": concern_level,
        "supporting_reviewers": ["openai"] if concern_level == "low" else ["openai", "claude"],
        "confidence_by_reviewer": {"openai": "medium"},
    }
    om.update(extra)
    return om


# ---------------------------------------------------------------------------
# Basic severity classification
# ---------------------------------------------------------------------------

def test_empty_forensics():
    result = rank_omissions({}, [], [])
    assert result == []


def test_non_dict_forensics():
    result = rank_omissions("garbage", [], [])
    assert result == []


def test_single_reviewer_no_critical_is_minor():
    sf = _sf(article_omissions=[_omission("article", "Some minor gap")])
    result = rank_omissions(sf, [], [])
    assert len(result) == 1
    assert result[0]["severity"] == "minor"


def test_elevated_concern_is_important():
    sf = _sf(article_omissions=[
        _omission("article", "Gap found by two reviewers", concern_level="elevated"),
    ])
    result = rank_omissions(sf, [], [])
    assert len(result) == 1
    assert result[0]["severity"] == "important"


def test_high_concern_is_important():
    sf = _sf(article_omissions=[
        _omission("article", "Gap found by all reviewers", concern_level="high"),
    ])
    result = rank_omissions(sf, [], [])
    assert len(result) == 1
    assert result[0]["severity"] == "important"


def test_targets_load_bearing_is_important():
    sf = _sf(claim_omissions=[
        _omission("claim", "Missing context for key claim", target_claim_id="G1"),
    ])
    result = rank_omissions(sf, ["G1"], [])
    assert len(result) == 1
    assert result[0]["severity"] == "important"


def test_targets_load_bearing_with_elevated_concern_is_load_bearing():
    sf = _sf(claim_omissions=[
        _omission("claim", "Missing context", concern_level="elevated", target_claim_id="G1"),
    ])
    result = rank_omissions(sf, ["G1"], [])
    assert len(result) == 1
    assert result[0]["severity"] == "load_bearing"


def test_targets_high_centrality_is_important():
    sf = _sf(claim_omissions=[
        _omission("claim", "Gap for central claim", target_claim_id="G1"),
    ])
    claims = [_claim("G1", centrality=3)]
    result = rank_omissions(sf, [], claims)
    assert len(result) == 1
    assert result[0]["severity"] == "important"


def test_affected_claim_ids_checked():
    sf = _sf(article_omissions=[
        _omission("article", "Article-level gap", affected_claim_ids=["G1"]),
    ])
    result = rank_omissions(sf, ["G1"], [])
    assert len(result) == 1
    assert result[0]["severity"] == "important"


# ---------------------------------------------------------------------------
# Fragility boost
# ---------------------------------------------------------------------------

def test_fragility_boost_single_reviewer():
    """High fragility + substantive text → boosted to important."""
    sf = _sf(
        article_omissions=[
            _omission("article", "This is a substantive omission about missing Palestinian perspective"),
        ],
        argument_integrity={
            "merged_argument_fragility": "high",
        },
    )
    result = rank_omissions(sf, [], [])
    assert len(result) == 1
    assert result[0]["severity"] == "important"
    assert "fragility boost" in result[0]["severity_reason"]


def test_fragility_boost_requires_substantive_text():
    """Short text is not boosted even with high fragility."""
    sf = _sf(
        article_omissions=[
            _omission("article", "Short gap"),
        ],
        argument_integrity={
            "merged_argument_fragility": "high",
        },
    )
    result = rank_omissions(sf, [], [])
    assert len(result) == 1
    assert result[0]["severity"] == "minor"


def test_fragility_boost_elevated():
    """Elevated fragility also triggers boost."""
    sf = _sf(
        article_omissions=[
            _omission("article", "A longer description of a missing perspective that matters"),
        ],
        argument_integrity={
            "merged_argument_fragility": "elevated",
        },
    )
    result = rank_omissions(sf, [], [])
    assert len(result) == 1
    assert result[0]["severity"] == "important"


def test_no_fragility_boost_when_low():
    """Low fragility does not trigger boost."""
    sf = _sf(
        article_omissions=[
            _omission("article", "A longer description of a missing perspective that matters"),
        ],
        argument_integrity={
            "merged_argument_fragility": "low",
        },
    )
    result = rank_omissions(sf, [], [])
    assert len(result) == 1
    assert result[0]["severity"] == "minor"


def test_fragility_boost_does_not_override_load_bearing():
    """Critical + elevated concern → load_bearing, not just important from boost."""
    sf = _sf(
        claim_omissions=[
            _omission("claim", "A substantive gap for a load-bearing claim",
                       concern_level="elevated", target_claim_id="G1"),
        ],
        argument_integrity={
            "merged_argument_fragility": "high",
        },
    )
    result = rank_omissions(sf, ["G1"], [])
    assert len(result) == 1
    assert result[0]["severity"] == "load_bearing"


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def test_sorting_by_severity_then_reviewer_count():
    sf = _sf(
        article_omissions=[
            _omission("article", "Minor gap", concern_level="low"),
            _omission("article", "Important gap", concern_level="elevated"),
        ],
        claim_omissions=[
            _omission("claim", "Load-bearing gap", concern_level="high", target_claim_id="G1"),
        ],
    )
    result = rank_omissions(sf, ["G1"], [])
    severities = [r["severity"] for r in result]
    assert severities == ["load_bearing", "important", "minor"]


# ---------------------------------------------------------------------------
# Kind labels
# ---------------------------------------------------------------------------

def test_kind_labels_assigned():
    sf = _sf(
        article_omissions=[_omission("article", "A")],
        framing_omissions=[_omission("framing", "B")],
        claim_omissions=[_omission("claim", "C", target_claim_id="X")],
    )
    result = rank_omissions(sf, [], [])
    kinds = sorted(r["kind"] for r in result)
    assert kinds == ["article_omission", "claim_omission", "framing_omission"]


# ---------------------------------------------------------------------------
# Mixed scenario
# ---------------------------------------------------------------------------

def test_realistic_advocacy_article():
    """
    Realistic scenario: advocacy article with high fragility.
    Multiple single-reviewer omissions should be boosted to important.
    """
    sf = _sf(
        article_omissions=[
            _omission("article", "Palestinian historical experience and perspective entirely absent"),
            _omission("article", "Non-antisemitic forms of anti-Zionism not discussed or acknowledged"),
            _omission("article", "Internal Israeli dissent and peace movement perspectives missing"),
        ],
        framing_omissions=[
            _omission("framing", "International law frameworks for evaluating claims not referenced"),
        ],
        argument_integrity={
            "merged_argument_fragility": "high",
        },
    )
    result = rank_omissions(sf, [], [])
    assert len(result) == 4
    important_count = sum(1 for r in result if r["severity"] == "important")
    assert important_count == 4  # all boosted by fragility
