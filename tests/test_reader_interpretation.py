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
    """Empty dict → minimal usable fallback (not 'Not assessed.')."""
    result = interpret_for_reader({})
    assert result["block_count"] == 0
    assert result["mechanism_blocks"] == []
    # Empty dict still has a valid enriched structure — should produce a fallback
    # containing the classification or a generic description
    assert len(result["bottom_line_plain"]) > 0
    assert result["bottom_line_plain"] != "Not assessed."


def test_non_dict_input():
    """Non-dict input → hard fallback 'Not assessed.'."""
    result = interpret_for_reader("garbage")
    assert result["block_count"] == 0
    assert result["bottom_line_plain"] == "Not assessed."


def test_non_dict_input_none():
    """None input → hard fallback."""
    result = interpret_for_reader(None)
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
    # Both example claims should appear in the body
    assert "X caused Y" in block["body"]
    assert "A led to B" in block["body"]
    # Body should reference causal language
    assert "causal" in block["body"].lower()


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
    # Should reference the omission text
    assert "Missing context A" in block["body"]
    # Should mention rival narratives
    assert "rival" in block["body"].lower() or "explanation" in block["body"].lower()


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
# Test: block structure and source traceability
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


def test_source_signals_non_empty():
    """Every mechanism block must have non-empty source_signals for traceability."""
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "X caused Y"},
        ],
        official_detections=[
            {"official_only": True, "claim_text": "Officials said Z"},
        ],
        baseline_detections=[
            {"baseline_absent": True, "claim_text": "Crime up 50%"},
        ],
    )
    result = interpret_for_reader(enriched)
    assert result["block_count"] >= 1
    for block in result["mechanism_blocks"]:
        assert isinstance(block["source_signals"], list)
        assert len(block["source_signals"]) > 0, (
            f"Block '{block['mechanism']}' has empty source_signals"
        )
        # Each source signal should have a type field
        for sig in block["source_signals"]:
            assert "type" in sig, (
                f"Source signal in '{block['mechanism']}' missing 'type' key"
            )


def test_source_signals_reflect_detector_family():
    """source_signals type should relate to the mechanism that produced it."""
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "X caused Y"},
        ],
    )
    result = interpret_for_reader(enriched)
    block = next(b for b in result["mechanism_blocks"] if b["mechanism"] == "unsupported_causal")
    signal_types = [s["type"] for s in block["source_signals"]]
    assert any("causal" in t for t in signal_types)


# ---------------------------------------------------------------------------
# Test: detector ordering
# ---------------------------------------------------------------------------

def test_detector_ordering():
    """Detectors run in priority order: omission_dependence before unsupported_causal."""
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
    # Both must fire for ordering to be testable
    assert "omission_dependence" in mechanisms
    assert "unsupported_causal" in mechanisms
    assert mechanisms.index("omission_dependence") < mechanisms.index("unsupported_causal")


# ---------------------------------------------------------------------------
# Test: duplicate mechanism suppression
# ---------------------------------------------------------------------------

def test_duplicate_mechanism_suppression():
    """Multiple detections of the same type produce exactly one block."""
    enriched = _base_enriched(
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "X caused Y"},
            {"unsupported_causal": True, "claim_text": "A led to B"},
            {"unsupported_causal": True, "claim_text": "C triggered D"},
        ],
    )
    result = interpret_for_reader(enriched)
    causal_blocks = [
        b for b in result["mechanism_blocks"] if b["mechanism"] == "unsupported_causal"
    ]
    assert len(causal_blocks) == 1, (
        f"Expected 1 unsupported_causal block, got {len(causal_blocks)}"
    )


def test_duplicate_omission_blocks():
    """Multiple omissions produce exactly one omission_dependence block."""
    enriched = _base_enriched(
        ranked_omissions=[
            {"severity": "load_bearing", "kind": "article_omission", "merged_text": "Missing A"},
            {"severity": "load_bearing", "kind": "article_omission", "merged_text": "Missing B"},
            {"severity": "important", "kind": "framing_omission", "merged_text": "Missing C"},
        ],
    )
    result = interpret_for_reader(enriched)
    omission_blocks = [
        b for b in result["mechanism_blocks"] if b["mechanism"] == "omission_dependence"
    ]
    assert len(omission_blocks) <= 1


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


# ---------------------------------------------------------------------------
# Test: realistic composite article fixture
# ---------------------------------------------------------------------------

def test_realistic_mobilizing_article():
    """
    Realistic fixture: mobilizing article with unsupported causal claims,
    omission dependence, official reliance, rejected load-bearing claim,
    and high fragility. Tests that the full interpretation pipeline produces
    a coherent multi-mechanism result.
    """
    claims = [
        _make_claim("G1", "The crisis was caused by foreign interference",
                     adjudication="rejected", centrality=3),
        _make_claim("G2", "Government response prevented further damage",
                     adjudication="kept", centrality=3, evidence_eids=["E1"]),
        _make_claim("G3", "Opposition leaders delayed action",
                     adjudication="downgraded", centrality=2),
        _make_claim("G4", "Economic indicators showed stability",
                     adjudication="kept", centrality=1, evidence_eids=["E2"]),
    ]
    enriched = _base_enriched(
        adjudicated_whole_article_judgment={
            "classification": "mobilizing",
            "confidence": "high",
        },
        adjudicated_claims=claims,
        causal_detections=[
            {"unsupported_causal": True, "claim_text": "The crisis was caused by foreign interference"},
        ],
        official_detections=[
            {"official_only": True, "claim_text": "Government response prevented further damage"},
        ],
        baseline_detections=[
            {"baseline_absent": True, "claim_text": "Economic indicators showed stability"},
        ],
        ranked_omissions=[
            {"severity": "load_bearing", "kind": "article_omission",
             "merged_text": "No independent sources corroborate the foreign interference claim"},
            {"severity": "important", "kind": "framing_omission",
             "merged_text": "Domestic policy failures as alternative explanation",
             "frame_used_by_article": "External threat narrative"},
            {"severity": "important", "kind": "claim_omission",
             "merged_text": "Opposition's stated reasons for delay"},
        ],
        structural_forensics={
            "rival_narratives": [
                {"lens": "Domestic policy failure explanation"},
            ],
        },
        load_bearing={
            "load_bearing_group_ids": ["G1", "G2"],
            "weak_link_group_ids": ["G1"],
            "argument_fragility": "high",
        },
        reads_like={
            "label": "a pattern often seen in propaganda",
            "flags": {
                "has_omission_dependence": True,
                "has_high_fragility": True,
                "has_framing_escalation": True,
                "has_official_reliance": True,
                "has_reassurance_pattern": True,
            },
            "matched_rule": 1,
        },
    )
    result = interpret_for_reader(enriched)

    # Multiple mechanisms should fire
    assert result["block_count"] >= 3, (
        f"Expected >= 3 mechanisms, got {result['block_count']}: "
        f"{[b['mechanism'] for b in result['mechanism_blocks']]}"
    )

    mechanisms = [b["mechanism"] for b in result["mechanism_blocks"]]

    # Core mechanisms expected for this article
    assert "unsupported_causal" in mechanisms
    assert "omission_dependence" in mechanisms
    assert "load_bearing_weakness" in mechanisms

    # Bottom line should reference mobilizing classification
    assert "mobilizing" in result["bottom_line_plain"]

    # Bottom line should reference fragility
    assert "fragile" in result["bottom_line_plain"].lower()

    # Every block should have traceable source_signals
    for block in result["mechanism_blocks"]:
        assert len(block["source_signals"]) > 0

    # Each mechanism should have a non-empty title and body
    for block in result["mechanism_blocks"]:
        assert len(block["title"]) > 0
        assert len(block["body"]) > 10  # more than a stub
