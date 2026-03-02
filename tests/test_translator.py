#!/usr/bin/env python3
"""
FILE: tests/test_translator.py
PURPOSE:
Tests for the universal translator + repair gate (engine/core/translator.py).

CONTRACT:
- Deterministic and offline: mock call_reviewer_fn, no network, no file I/O.
- Tests match coordinator acceptance criteria T1-T7.
"""

import copy
import json
import pytest

from engine.core.errors import ReviewerPackCompileError
from engine.core.translator import compile_reviewer_pack
from engine.core.translation_rules import (
    CANONICAL_ENUMS,
    translate_field,
    build_enum_contract_text,
    normalize_format,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CFG = {
    "max_claims_per_reviewer": 20,
    "max_near_duplicate_links": 3,
    "reviewers_enabled": ["openai", "gemini"],
    "confidence_weights": {"low": 0.5, "medium": 1.0, "high": 1.5},
    "model_weights": {"openai": 1.0, "gemini": 1.0},
    "decision_margin": 0.2,
}


def _make_valid_pack(reviewer="openai"):
    return {
        "reviewer": reviewer,
        "whole_article_judgment": {
            "classification": "analysis",
            "confidence": "high",
            "evidence_eids": ["E1"],
        },
        "main_conclusion": {"text": "The article argues X."},
        "claims": [
            {
                "claim_id": f"{reviewer}-C1",
                "text": "A factual claim.",
                "type": "factual",
                "evidence_eids": ["E1"],
                "centrality": 1,
            },
        ],
        "scope_markers": [],
        "causal_links": [],
        "article_patterns": [],
        "omission_candidates": [],
        "counterfactual_requirements": [],
        "evidence_density": {
            "claims_count": 1,
            "claims_with_internal_support": 1,
            "external_sources_count": 0,
        },
        "claim_tickets": [],
        "article_tickets": [],
        "cross_claim_votes": [],
    }


def _never_called(system_prompt, user_prompt):
    """Mock call_reviewer_fn that should never be invoked."""
    raise AssertionError("call_reviewer_fn should not have been called")


# ---------------------------------------------------------------------------
# T1: Invalid enum triggers repair, canonical value produced
# ---------------------------------------------------------------------------

def test_invalid_enum_triggers_repair_and_produces_canonical():
    """Pack with 'opinion' classification (not a canonical value) triggers repair."""
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "opinion"  # invalid

    call_count = [0]

    def mock_repair(system_prompt, user_prompt):
        call_count[0] += 1
        # Repair: return a corrected pack
        fixed = _make_valid_pack()
        fixed["whole_article_judgment"]["classification"] = "analysis"
        return fixed

    result = compile_reviewer_pack(
        reviewer_id="gemini",
        raw_pack=pack,
        call_reviewer_fn=mock_repair,
        config=_CFG,
    )

    assert call_count[0] == 1, "Repair should have been called exactly once"
    assert result["whole_article_judgment"]["classification"] == "analysis"


# ---------------------------------------------------------------------------
# T2: Valid pack passes through without repair (0 calls)
# ---------------------------------------------------------------------------

def test_valid_pack_no_repair_needed():
    pack = _make_valid_pack()

    result = compile_reviewer_pack(
        reviewer_id="openai",
        raw_pack=pack,
        call_reviewer_fn=_never_called,
        config=_CFG,
    )

    assert result["whole_article_judgment"]["classification"] == "analysis"
    assert result["claims"][0]["type"] == "factual"


# ---------------------------------------------------------------------------
# T3: Pack invalid after repair raises ReviewerPackCompileError
# ---------------------------------------------------------------------------

def test_invalid_after_repair_raises_compile_error():
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "garbage_value"

    def mock_bad_repair(system_prompt, user_prompt):
        # Repair also returns garbage
        broken = _make_valid_pack()
        broken["whole_article_judgment"]["classification"] = "still_garbage"
        return broken

    with pytest.raises(ReviewerPackCompileError) as exc_info:
        compile_reviewer_pack(
            reviewer_id="gemini",
            raw_pack=pack,
            call_reviewer_fn=mock_bad_repair,
            config=_CFG,
        )

    err = exc_info.value
    assert err.reviewer_id == "gemini"
    assert err.attempt == 2
    assert len(err.validation_errors) > 0
    assert len(err.translation_trace) > 0

    # Debug dict serializes cleanly
    debug = err.to_debug_dict()
    assert debug["reviewer_id"] == "gemini"
    assert debug["attempt"] == 2


# ---------------------------------------------------------------------------
# T4: raw_* fields preserved on translated pack
# ---------------------------------------------------------------------------

def test_raw_fields_preserved():
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "Analysis"  # uppercase

    result = compile_reviewer_pack(
        reviewer_id="openai",
        raw_pack=pack,
        call_reviewer_fn=_never_called,
        config=_CFG,
    )

    waj = result["whole_article_judgment"]
    assert waj["classification"] == "analysis"  # translated to lowercase
    assert waj["raw_classification_label"] == "Analysis"  # original preserved


def test_raw_fields_on_claims():
    pack = _make_valid_pack()
    pack["claims"][0]["type"] = "Factual"  # uppercase

    result = compile_reviewer_pack(
        reviewer_id="openai",
        raw_pack=pack,
        call_reviewer_fn=_never_called,
        config=_CFG,
    )

    assert result["claims"][0]["type"] == "factual"
    assert result["claims"][0]["raw_type_label"] == "Factual"


# ---------------------------------------------------------------------------
# T5: Namespace violation caught
# ---------------------------------------------------------------------------

def test_namespace_violation_gsae_bucket_in_classification():
    """GSAE bucket vocabulary in article classification triggers failure."""
    pack = _make_valid_pack()
    # "interpretive" is a GSAE bucket, forbidden in article classification
    pack["whole_article_judgment"]["classification"] = "interpretive"

    def mock_repair(system_prompt, user_prompt):
        fixed = _make_valid_pack()
        fixed["whole_article_judgment"]["classification"] = "analysis"
        return fixed

    result = compile_reviewer_pack(
        reviewer_id="gemini",
        raw_pack=pack,
        call_reviewer_fn=mock_repair,
        config=_CFG,
    )

    assert result["whole_article_judgment"]["classification"] == "analysis"


# ---------------------------------------------------------------------------
# T6: Diff guard — substantive fields unchanged across repair
# ---------------------------------------------------------------------------

def test_repair_preserves_substantive_fields():
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "nonsense"
    original_claim_text = pack["claims"][0]["text"]
    original_conclusion = pack["main_conclusion"]["text"]

    def mock_repair(system_prompt, user_prompt):
        fixed = copy.deepcopy(pack)
        fixed["whole_article_judgment"]["classification"] = "reporting"
        return fixed

    result = compile_reviewer_pack(
        reviewer_id="gemini",
        raw_pack=pack,
        call_reviewer_fn=mock_repair,
        config=_CFG,
    )

    assert result["claims"][0]["text"] == original_claim_text
    assert result["main_conclusion"]["text"] == original_conclusion


def test_diff_guard_blocks_claim_text_change():
    """Repair that changes claim text is rejected by diff guard."""
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "nonsense"

    def mock_sneaky_repair(system_prompt, user_prompt):
        fixed = _make_valid_pack()
        fixed["whole_article_judgment"]["classification"] = "reporting"
        # Sneaky: model also changed claim text during "repair"
        fixed["claims"][0]["text"] = "A completely different claim."
        return fixed

    with pytest.raises(ReviewerPackCompileError) as exc_info:
        compile_reviewer_pack(
            reviewer_id="gemini",
            raw_pack=pack,
            call_reviewer_fn=mock_sneaky_repair,
            config=_CFG,
        )

    err = exc_info.value
    assert any("diff_guard" in e.get("path", "") for e in err.validation_errors)
    assert any("text" in e.get("got", "") for e in err.validation_errors)


def test_diff_guard_blocks_conclusion_change():
    """Repair that changes main_conclusion is rejected."""
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "nonsense"

    def mock_sneaky_repair(system_prompt, user_prompt):
        fixed = _make_valid_pack()
        fixed["whole_article_judgment"]["classification"] = "reporting"
        fixed["main_conclusion"]["text"] = "Totally rewritten conclusion."
        return fixed

    with pytest.raises(ReviewerPackCompileError) as exc_info:
        compile_reviewer_pack(
            reviewer_id="gemini",
            raw_pack=pack,
            call_reviewer_fn=mock_sneaky_repair,
            config=_CFG,
        )

    err = exc_info.value
    assert any("main_conclusion" in e.get("got", "") for e in err.validation_errors)


def test_diff_guard_blocks_evidence_eid_change():
    """Repair that changes evidence_eids is rejected."""
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "nonsense"

    def mock_sneaky_repair(system_prompt, user_prompt):
        fixed = _make_valid_pack()
        fixed["whole_article_judgment"]["classification"] = "reporting"
        fixed["whole_article_judgment"]["evidence_eids"] = ["E99"]
        return fixed

    with pytest.raises(ReviewerPackCompileError) as exc_info:
        compile_reviewer_pack(
            reviewer_id="gemini",
            raw_pack=pack,
            call_reviewer_fn=mock_sneaky_repair,
            config=_CFG,
        )

    err = exc_info.value
    assert any("evidence_eids" in e.get("got", "") for e in err.validation_errors)


# ---------------------------------------------------------------------------
# T7: Mock call_reviewer_fn returns fixed JSON on repair
# ---------------------------------------------------------------------------

def test_repair_call_receives_error_and_enum_contract():
    pack = _make_valid_pack()
    pack["claims"][0]["type"] = "stated_position"  # not canonical, not lossless alias

    captured_prompts = []

    def mock_repair(system_prompt, user_prompt):
        captured_prompts.append((system_prompt, user_prompt))
        fixed = _make_valid_pack()
        fixed["claims"][0]["type"] = "normative"
        return fixed

    result = compile_reviewer_pack(
        reviewer_id="gemini",
        raw_pack=pack,
        call_reviewer_fn=mock_repair,
        config=_CFG,
    )

    assert len(captured_prompts) == 1
    system_prompt, user_prompt = captured_prompts[0]

    # Repair prompt contains the error
    assert "stated_position" in user_prompt
    assert "claims" in user_prompt

    # Repair prompt contains enum contract
    assert "ALLOWED ENUM VALUES" in user_prompt

    assert result["claims"][0]["type"] == "normative"


# ---------------------------------------------------------------------------
# Lossless alias tests
# ---------------------------------------------------------------------------

def test_lossless_alias_propaganda_patterned_advocacy():
    """Underscore variant of 'propaganda-patterned advocacy' is lossless alias."""
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "propaganda_patterned_advocacy"

    result = compile_reviewer_pack(
        reviewer_id="openai",
        raw_pack=pack,
        call_reviewer_fn=_never_called,
        config=_CFG,
    )

    assert result["whole_article_judgment"]["classification"] == "propaganda-patterned advocacy"


def test_lossless_alias_confidence_band_hyphen():
    """sb-low → sb_low is a lossless formatting alias."""
    canonical, raw, ok = translate_field("gsae_observation.confidence_band", "sb-low")
    assert ok is True
    assert canonical == "sb_low"


# ---------------------------------------------------------------------------
# translate_field unit tests
# ---------------------------------------------------------------------------

def test_translate_field_canonical_passthrough():
    canonical, raw, ok = translate_field("whole_article_judgment.classification", "reporting")
    assert ok is True
    assert canonical == "reporting"


def test_translate_field_unknown_fails():
    canonical, raw, ok = translate_field("whole_article_judgment.classification", "banana")
    assert ok is False
    assert canonical is None
    assert raw == "banana"


def test_translate_field_namespace_violation():
    # "mobilizing" is a GSAE bucket, forbidden in article classification
    canonical, raw, ok = translate_field("whole_article_judgment.classification", "mobilizing")
    assert ok is False


def test_translate_field_unknown_path_passthrough():
    canonical, raw, ok = translate_field("unknown.path", "anything")
    assert ok is True
    assert canonical == "anything"


# ---------------------------------------------------------------------------
# expression block allowed through validation
# ---------------------------------------------------------------------------

def test_expression_block_allowed():
    pack = _make_valid_pack()
    pack["expression"] = {
        "alternate_labels": {"classification": "propaganda-like advocacy"},
        "commentary": "The article uses mobilizing rhetoric but within advocacy framing.",
    }

    result = compile_reviewer_pack(
        reviewer_id="openai",
        raw_pack=pack,
        call_reviewer_fn=_never_called,
        config=_CFG,
    )

    assert "expression" in result
    assert result["expression"]["commentary"].startswith("The article")


def test_repair_adding_expression_allowed():
    """Repair that adds expression block (absent in attempt 1) passes diff guard."""
    pack = _make_valid_pack()
    pack["whole_article_judgment"]["classification"] = "nonsense"
    # No "expression" key in original pack

    def mock_repair(system_prompt, user_prompt):
        fixed = _make_valid_pack()
        fixed["whole_article_judgment"]["classification"] = "reporting"
        fixed["expression"] = {"commentary": "Nuance beyond the enum."}
        return fixed

    result = compile_reviewer_pack(
        reviewer_id="gemini",
        raw_pack=pack,
        call_reviewer_fn=mock_repair,
        config=_CFG,
    )

    assert result["whole_article_judgment"]["classification"] == "reporting"
    assert "expression" in result


# ---------------------------------------------------------------------------
# build_enum_contract_text
# ---------------------------------------------------------------------------

def test_build_enum_contract_text_contains_all_paths():
    text = build_enum_contract_text()
    assert "ALLOWED ENUM VALUES" in text
    assert "whole_article_judgment.classification" in text
    assert "claims.type" in text
    assert "reporting" in text
