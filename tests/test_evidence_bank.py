#!/usr/bin/env python3
"""
FILE: tests/test_evidence_bank.py
PURPOSE:
Verify the canonical EvidenceBank schema (v0.2).

Behavioral contracts tested:
  - Envelope: items, used_chars, max_chars
  - quote == source_text[char_start:char_end]  (verbatim slice invariant)
  - locator: char_start/char_end are ints pointing into the original text
  - source_id present and matches argument; default is "A1"
  - eid is sequential: E1, E2, ...
  - Transitional aliases: text == quote, char_len == len(quote)
  - max_chars cap: used_chars <= max_chars, chunking halts at cap
  - Empty / whitespace-only input → items=[], used_chars=0
  - Leading whitespace per line stripped in quote; locator tracks stripped start
  - Fail-closed: corrupted slice raises RuntimeError matching "locator mismatch"

Run with: python -m pytest tests/ -v
"""

import pytest

from engine.core.evidence_bank import build_evidence_bank


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CFG = {"max_chars": 2400}


def _bank(text: str, *, source_id: str = "A1", max_chars: int = 2400):
    return build_evidence_bank(text, {"max_chars": max_chars}, source_id=source_id)


_MULTI = "The quick brown fox.\nJumped over the lazy dog.\nEnd of story."


# ---------------------------------------------------------------------------
# Envelope structure
# ---------------------------------------------------------------------------


def test_envelope_has_required_keys():
    result = _bank("Hello world.")
    assert "items" in result
    assert "used_chars" in result
    assert "max_chars" in result


def test_envelope_max_chars_matches_config():
    result = _bank("Hello world.", max_chars=500)
    assert result["max_chars"] == 500


# ---------------------------------------------------------------------------
# Schema: canonical fields present
# ---------------------------------------------------------------------------


def test_item_has_canonical_fields():
    result = _bank("First sentence.\nSecond sentence.")
    item = result["items"][0]
    assert "eid" in item
    assert "quote" in item
    assert "locator" in item
    assert "source_id" in item


def test_locator_has_char_start_and_char_end():
    result = _bank("Alpha.\nBeta.")
    for item in result["items"]:
        assert "char_start" in item["locator"]
        assert "char_end" in item["locator"]
        assert isinstance(item["locator"]["char_start"], int)
        assert isinstance(item["locator"]["char_end"], int)


def test_item_has_transitional_aliases():
    result = _bank("Sample line.")
    item = result["items"][0]
    assert "text" in item, "transitional alias 'text' must be present"
    assert "char_len" in item, "transitional alias 'char_len' must be present"


# ---------------------------------------------------------------------------
# Verbatim slice invariant
# ---------------------------------------------------------------------------


def test_quote_equals_source_text_slice():
    """Core invariant: quote == source_text[char_start:char_end]."""
    text = _MULTI
    result = build_evidence_bank(text, _CFG)
    for item in result["items"]:
        cs = item["locator"]["char_start"]
        ce = item["locator"]["char_end"]
        assert item["quote"] == text[cs:ce], (
            f"{item['eid']}: quote does not match source_text slice"
        )


def test_text_alias_equals_quote():
    result = _bank(_MULTI)
    for item in result["items"]:
        assert item["text"] == item["quote"]


def test_char_len_alias_equals_len_of_quote():
    result = _bank(_MULTI)
    for item in result["items"]:
        assert item["char_len"] == len(item["quote"])


def test_quote_is_nonempty():
    result = _bank(_MULTI)
    for item in result["items"]:
        assert item["quote"].strip(), f"{item['eid']}: quote must not be empty"


# ---------------------------------------------------------------------------
# eid sequencing
# ---------------------------------------------------------------------------


def test_eid_sequential_from_e1():
    result = _bank("Line one.\nLine two.\nLine three.")
    for idx, item in enumerate(result["items"], start=1):
        assert item["eid"] == f"E{idx}", f"Expected E{idx}, got {item['eid']}"


# ---------------------------------------------------------------------------
# source_id
# ---------------------------------------------------------------------------


def test_source_id_default_is_a1():
    result = build_evidence_bank("Some text.", _CFG)
    assert result["items"][0]["source_id"] == "A1"


def test_source_id_propagated_to_all_items():
    result = _bank("Line A.\nLine B.\nLine C.", source_id="A7")
    for item in result["items"]:
        assert item["source_id"] == "A7"


# ---------------------------------------------------------------------------
# max_chars cap
# ---------------------------------------------------------------------------


def test_max_chars_cap_respected():
    text = "\n".join([f"Word{i} sentence padding text here." for i in range(50)])
    cap = 200
    result = _bank(text, max_chars=cap)
    assert result["used_chars"] <= cap, (
        f"used_chars {result['used_chars']} exceeds cap {cap}"
    )


def test_max_chars_produces_fewer_items_than_lines():
    lines = [f"Line number {i} with some content." for i in range(20)]
    text = "\n".join(lines)
    full = _bank(text)
    capped = _bank(text, max_chars=100)
    assert len(capped["items"]) < len(full["items"])


# ---------------------------------------------------------------------------
# Edge cases: empty / whitespace
# ---------------------------------------------------------------------------


def test_empty_string_produces_no_items():
    result = _bank("")
    assert result["items"] == []
    assert result["used_chars"] == 0


def test_whitespace_only_produces_no_items():
    result = _bank("   \n\n\t  \n  ")
    assert result["items"] == []
    assert result["used_chars"] == 0


# ---------------------------------------------------------------------------
# Single line
# ---------------------------------------------------------------------------


def test_single_line_quote_and_eid():
    text = "Exactly one line."
    result = _bank(text)
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["eid"] == "E1"
    assert item["quote"] == "Exactly one line."


def test_single_line_locator_bounds():
    text = "Exactly one line."
    result = _bank(text)
    item = result["items"][0]
    assert item["locator"]["char_start"] == 0
    assert item["locator"]["char_end"] == len("Exactly one line.")


# ---------------------------------------------------------------------------
# Leading whitespace: stripped in quote; locator tracks stripped start
# ---------------------------------------------------------------------------


def test_leading_whitespace_stripped_in_quote():
    text = "   Indented line here."
    result = _bank(text)
    item = result["items"][0]
    assert item["quote"] == "Indented line here."
    # Locator must point into the ORIGINAL text string
    cs = item["locator"]["char_start"]
    ce = item["locator"]["char_end"]
    assert text[cs:ce] == item["quote"]


def test_locator_bounds_within_text_length():
    text = "Short.\nMedium line here.\nLonger final line of text."
    result = _bank(text)
    for item in result["items"]:
        cs = item["locator"]["char_start"]
        ce = item["locator"]["char_end"]
        assert cs >= 0
        assert ce <= len(text)
        assert cs < ce


# ---------------------------------------------------------------------------
# Fail-closed: locator mismatch raises RuntimeError
# ---------------------------------------------------------------------------


def test_locator_mismatch_raises_runtime_error():
    """
    Pass a str subclass whose __getitem__ corrupts slices.
    build_evidence_bank() re-slices to verify the locator; the corrupted
    result must not match the extracted quote, triggering RuntimeError.
    """

    class CorruptedStr(str):
        def __getitem__(self, key):
            result = super().__getitem__(key)
            if isinstance(result, str) and result:
                return result + "\x00CORRUPTED"
            return result

    text = CorruptedStr("Legitimate evidence line.")

    with pytest.raises(RuntimeError, match="locator mismatch"):
        build_evidence_bank(text, _CFG)
