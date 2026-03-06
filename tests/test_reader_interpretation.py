#!/usr/bin/env python3
"""Tests for engine.analysis.reader_interpretation."""

import pytest

from engine.analysis.reader_interpretation import interpret_for_reader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_enriched(**overrides):
    """Minimal enriched substrate with defaults that fire nothing."""
    base = {
        "adjudicated_whole_article_judgment": {
            "classification": "reporting",
            "confidence": "high",
        },
        "adjudicated_claims": [],
        "causal_detections": [],
        "baseline_detections": [],
        "official_detections": [],
        "ranked_omissions": [],
        "structural_forensics": {},
        "load_bearing": {
            "load_bearing_group_ids": [],
            "weak_link_group_ids": [],
            "argument_fragility": "low",
        },
        "reads_like": {
            "label": "reporting with minor structural concerns",
            "flags": {},
            "matched_rule": 6,
        },
    }
    base.update(overrides)
    return base


def _make_claim(group_id, text, adjudication="kept", centrality=2, evidence_eids=None):
    return {
        "group_id": group_id,
        "member_claim_ids": [f"{group_id}-m1"],
        "text": text,
        "adjudication": adjudication,
        "centrality": centrality,
        "evidence_eids": evidence_eids or [],
    }


# ---------------------------------------------------------------------------
# Test: empty / invalid input
# ---------------------------------------------------------------------------

def test_empty_input():
    result = interpret_for_reader({})
    assert result["block_count"] == 0
    assert result["mechanism_blocks"] == []
    assert "Not assessed" not in result["bottom_line_plain"]  # should still produce something


def test_non_dict_input():
    result = interpret_for_reader("garbage")
    assert result["block_count"] == 0
    assert result["bottom_line_plain"] == "Not assessed."


def test_no_mechanisms_fire():
    result = interpret_for_reader(_base_enriched())
    assert result["block_count"] == 0
    assert "reporting" in result["bottom_line_plain"].lower()


# ---------------------------------------------------------------------------
# Test: unsupported causal detector
# ---------------------------------------------------------------------------

def test_unsupported_causal_fires():
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "X caused Y"},
            {"unsupported_causal": True, "claim_text": "A led to B"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "unsupported_causal" in mechanisms

    block = next(b for b in result["mechanism_blocks"] if b["mechanism"] == "unsupported_causal")
    assert "2 causal claim" in block["body"]
    assert "X caused Y" in block["body"]


def test_supported_causal_does_not_fire():
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": False, "claim_text": "X caused Y"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "unsupported_causal" not in mechanisms


# ---------------------------------------------------------------------------
# Test: omission dependence detector
# ---------------------------------------------------------------------------

def test_omission_dependence_fires():
    enriched = _base_enriched(
        ranked_omissions=[
            {"severity": "load_bearing", "kind": "article_omission", "merged_text": "Missing context A"},
            {"severity": "important", "kind": "framing_omission", "merged_text": "Missing frame B"},
        ],
        structural_forensics={"rival_narratives": [{"lens": "alt explanation"}]},
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "omission_dependence" in mechanisms

    block = next(b for b in result["mechanism_blocks"] if b["mechanism"] == "omission_dependence")
    assert "2 significant" in block["body"]
    assert "Missing context A" in block["body"]


def test_omission_dependence_skips_minor():
    enriched = _base_enriched(
        ranked_omissions=[
            {"severity": "minor", "kind": "article_omission", "merged_text": "trivial"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "omission_dependence" not in mechanisms


# ---------------------------------------------------------------------------
# Test: framing escalation detector
# ---------------------------------------------------------------------------

def test_framing_escalation_fires():
    enriched = _base_enriched(
        ranked_omissions=[
            {
                "severity": "load_bearing",
                "kind": "framing_omission",
                "merged_text": "Missing frame",
                "frame_used_by_article": "Threat frame",
            },
        ],
        load_bearing={
            "load_bearing_group_ids": ["G1"],
            "weak_link_group_ids": [],
            "argument_fragility": "high",
        },
        reads_like={
            "label": "test",
            "flags": {"has_high_fragility": True, "has_reassurance_pattern": False},
            "matched_rule": 1,
        },
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "framing_escalation" in mechanisms


# ---------------------------------------------------------------------------
# Test: load-bearing weakness detector
# ---------------------------------------------------------------------------

def test_load_bearing_weakness_fires():
    claims = [
        _make_claim("G1", "Core claim", adjudication="rejected", centrality=3),
    ]
    enriched = _base_enriched(
        adjudicated_claims=claims,
        load_bearing={
            "load_bearing_group_ids": ["G1"],
            "weak_link_group_ids": [],
            "argument_fragility": "high",
        },
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "load_bearing_weakness" in mechanisms

    block = next(b for b in result["mechanism_blocks"] if b["mechanism"] == "load_bearing_weakness")
    assert "rejected" in block["body"]


def test_load_bearing_no_weakness():
    claims = [
        _make_claim("G1", "Solid claim", adjudication="kept", centrality=3),
    ]
    enriched = _base_enriched(
        adjudicated_claims=claims,
        load_bearing={
            "load_bearing_group_ids": ["G1"],
            "weak_link_group_ids": [],
            "argument_fragility": "low",
        },
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "load_bearing_weakness" not in mechanisms


# ---------------------------------------------------------------------------
# Test: official reliance detector
# ---------------------------------------------------------------------------

def test_official_reliance_fires():
    enriched = _base_enriched(
        official_detections=[
            {"official_only": True, "claim_text": "The government stated X"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "official_reliance" in mechanisms


def test_official_reliance_skips_non_official():
    enriched = _base_enriched(
        official_detections=[
            {"official_only": False, "claim_text": "Something"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "official_reliance" not in mechanisms


# ---------------------------------------------------------------------------
# Test: baseline absence detector
# ---------------------------------------------------------------------------

def test_baseline_absence_fires():
    enriched = _base_enriched(
        baseline_detections=[
            {"baseline_absent": True, "claim_text": "Crime increased 50%"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "baseline_absence" in mechanisms


def test_baseline_present_skips():
    enriched = _base_enriched(
        baseline_detections=[
            {"baseline_absent": False, "claim_text": "Crime increased 50% from 2020"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    assert "baseline_absence" not in mechanisms


# ---------------------------------------------------------------------------
# Test: bottom line synthesis
# ---------------------------------------------------------------------------

def test_bottom_line_includes_classification():
    enriched = _base_enriched(
        adjudicated_whole_article_judgment={
            "classification": "mobilizing",
            "confidence": "high",
        },
    )
    result = interpret_for_reader(enriched)
    assert "mobilizing" in result["bottom_line_plain"]


def test_bottom_line_with_multiple_mechanisms():
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "X caused Y"},
        ],
        ranked_omissions=[
            {"severity": "load_bearing", "kind": "article_omission", "merged_text": "Missing A"},
            {"severity": "important", "kind": "framing_omission", "merged_text": "Missing B"},
        ],
        adjudicated_claims=[
            _make_claim("G1", "Core claim", adjudication="rejected", centrality=3),
        ],
        load_bearing={
            "load_bearing_group_ids": ["G1"],
            "weak_link_group_ids": [],
            "argument_fragility": "high",
        },
    )
    result = interpret_for_reader(enriched)
    # Should fire multiple mechanisms
    assert result["block_count"] >= 2
    # Bottom line should mention fragility
    assert "fragile" in result["bottom_line_plain"].lower()


# ---------------------------------------------------------------------------
# Test: block structure
# ---------------------------------------------------------------------------

def test_block_has_required_keys():
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "Test claim"},
        ],
    )
    result = interpret_for_reader(enriched)
    for block in result["mechanism_blocks"]:
        assert "mechanism" in block
        assert "title" in block
        assert "body" in block
        assert "source_signals" in block


def test_detector_ordering():
    """Detectors run in priority order: omission_dependence first."""
    enriched = _base_enriched(
        ranked_omissions=[
            {"severity": "load_bearing", "kind": "article_omission", "merged_text": "Missing"},
            {"severity": "important", "kind": "article_omission", "merged_text": "Also missing"},
        ],
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "X caused Y"},
        ],
    )
    result = interpret_for_reader(enriched)
    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]
    # omission_dependence should come before unsupported_causal
    if "omission_dependence" in mechanisms and "unsupported_causal" in mechanisms:
        assert mechanisms.index("omission_dependence") < mechanisms.index("unsupported_causal")


# ---------------------------------------------------------------------------
# Test: reader guidance in bottom line
# ---------------------------------------------------------------------------

def test_reader_guidance_with_many_mechanisms():
    """When >= 3 mechanisms fire, bottom line includes reader guidance."""
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "X caused Y"},
        ],
        official_detections=[
            {"official_only": True, "claim_text": "Officials said Z"},
        ],
        ranked_omissions=[
            {"severity": "load_bearing", "kind": "article_omission", "merged_text": "Missing A"},
            {"severity": "important", "kind": "article_omission", "merged_text": "Missing B"},
        ],
    )
    result = interpret_for_reader(enriched)
    if result["block_count"] >= 3:
        assert "structure working" in result["bottom_line_plain"].lower()
