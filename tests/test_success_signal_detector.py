"""Tests for engine.analysis.success_signal_detector — SSD Phase 1."""

from engine.analysis.success_signal_detector import detect_success_signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enriched(
    claims=None,
    verification=None,
    reader_interpretation=None,
    waj=None,
):
    """Build minimal enriched substrate for SSD testing."""
    return {
        "adjudicated_claims": claims or [],
        "verification": verification or {},
        "reader_interpretation": reader_interpretation if reader_interpretation is not None else {},
        "adjudicated_whole_article_judgment": waj or {},
    }


def _claim(text: str) -> dict:
    return {"text": text}


def _verification_with(status: str) -> dict:
    return {"results": [{"verification_status": status}]}


# ---------------------------------------------------------------------------
# Comparative grounding
# ---------------------------------------------------------------------------

class TestComparativeGrounding:
    def test_baseline_detected(self):
        enriched = _enriched(claims=[_claim("Rates were higher than the baseline average.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "comparative_grounding" for b in blocks)

    def test_compared_with(self):
        enriched = _enriched(claims=[_claim("Compared with 2019, outcomes improved.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "comparative_grounding" for b in blocks)

    def test_versus(self):
        enriched = _enriched(claims=[_claim("Group A versus Group B showed differences.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "comparative_grounding" for b in blocks)

    def test_percentage_above(self):
        enriched = _enriched(claims=[_claim("Spending was 15% above the historical norm.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "comparative_grounding" for b in blocks)

    def test_no_emit_from_adjectives(self):
        enriched = _enriched(claims=[_claim("This is a unique and extreme situation.")])
        blocks = detect_success_signals(enriched)
        assert not any(b["mechanism"] == "comparative_grounding" for b in blocks)


# ---------------------------------------------------------------------------
# Scope discipline
# ---------------------------------------------------------------------------

class TestScopeDiscipline:
    def test_in_this_case(self):
        enriched = _enriched(claims=[_claim("In this case, the results were positive.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "scope_discipline" for b in blocks)

    def test_limited_to(self):
        enriched = _enriched(claims=[_claim("The findings are limited to urban areas.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "scope_discipline" for b in blocks)

    def test_only_shows(self):
        enriched = _enriched(claims=[_claim("This result only shows outcomes for this dataset.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "scope_discipline" for b in blocks)

    def test_cannot_generalize(self):
        enriched = _enriched(claims=[_claim("We cannot generalize from this sample.")])
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "scope_discipline" for b in blocks)

    def test_no_emit_from_absence_of_scope_inflation(self):
        enriched = _enriched(claims=[_claim("The economy grew last quarter.")])
        blocks = detect_success_signals(enriched)
        assert not any(b["mechanism"] == "scope_discipline" for b in blocks)


# ---------------------------------------------------------------------------
# Uncertainty visibility
# ---------------------------------------------------------------------------

class TestUncertaintyVisibility:
    def test_text_and_verification(self):
        enriched = _enriched(
            claims=[_claim("The evidence remains uncertain.")],
            verification=_verification_with("conflicted_sources"),
        )
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "uncertainty_visibility" for b in blocks)

    def test_not_established_and_not_verifiable(self):
        enriched = _enriched(
            claims=[_claim("The cause is not established.")],
            verification=_verification_with("not_verifiable"),
        )
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "uncertainty_visibility" for b in blocks)

    def test_waj_uncertain_and_verification(self):
        enriched = _enriched(
            claims=[_claim("The project had mixed results.")],
            verification=_verification_with("not_checked_yet"),
            waj={"classification": "uncertain"},
        )
        blocks = detect_success_signals(enriched)
        assert any(b["mechanism"] == "uncertainty_visibility" for b in blocks)

    def test_no_emit_text_only(self):
        """Text has uncertainty language but no unresolved verification."""
        enriched = _enriched(
            claims=[_claim("The outcome is uncertain.")],
            verification={"results": [{"verification_status": "verified_true"}]},
        )
        blocks = detect_success_signals(enriched)
        assert not any(b["mechanism"] == "uncertainty_visibility" for b in blocks)

    def test_no_emit_verification_only(self):
        """Unresolved verification but no uncertainty language in text."""
        enriched = _enriched(
            claims=[_claim("The company reported strong earnings.")],
            verification=_verification_with("conflicted_sources"),
        )
        blocks = detect_success_signals(enriched)
        assert not any(b["mechanism"] == "uncertainty_visibility" for b in blocks)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_same_mechanism_not_repeated(self):
        enriched = _enriched(claims=[
            _claim("Compared with the baseline, rates were higher than average.")
        ])
        blocks = detect_success_signals(enriched)
        cg = [b for b in blocks if b["mechanism"] == "comparative_grounding"]
        assert len(cg) == 1

    def test_multiple_mechanisms_can_fire(self):
        enriched = _enriched(claims=[
            _claim("Compared with 2020, results were higher than expected."),
            _claim("In this case, we cannot generalize the findings."),
        ])
        blocks = detect_success_signals(enriched)
        mechs = [b["mechanism"] for b in blocks]
        assert "comparative_grounding" in mechs
        assert "scope_discipline" in mechs


# ---------------------------------------------------------------------------
# Stable ordering
# ---------------------------------------------------------------------------

class TestStableOrder:
    def test_order_comparative_before_scope_before_uncertainty(self):
        enriched = _enriched(
            claims=[
                _claim("In this case the evidence is uncertain and higher than baseline."),
            ],
            verification=_verification_with("conflicted_sources"),
        )
        blocks = detect_success_signals(enriched)
        mechs = [b["mechanism"] for b in blocks]
        assert mechs.index("comparative_grounding") < mechs.index("scope_discipline")
        assert mechs.index("scope_discipline") < mechs.index("uncertainty_visibility")


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_none_input(self):
        assert detect_success_signals(None) == []

    def test_empty_claims(self):
        enriched = _enriched(claims=[])
        assert detect_success_signals(enriched) == []

    def test_no_text_in_claims(self):
        enriched = _enriched(claims=[{"group_id": "g1"}])
        assert detect_success_signals(enriched) == []

    def test_reader_interpretation_error(self):
        enriched = _enriched(
            claims=[_claim("Compared with last year, results improved.")],
            reader_interpretation={"error": "boom"},
        )
        assert detect_success_signals(enriched) == []

    def test_malformed_verification(self):
        enriched = _enriched(
            claims=[_claim("The outcome is uncertain.")],
            verification="not_a_dict",
        )
        blocks = detect_success_signals(enriched)
        assert not any(b["mechanism"] == "uncertainty_visibility" for b in blocks)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class TestOutputSchema:
    def test_block_has_required_keys(self):
        enriched = _enriched(claims=[_claim("Rates were higher than the baseline.")])
        blocks = detect_success_signals(enriched)
        assert len(blocks) >= 1
        block = blocks[0]
        assert "mechanism" in block
        assert "title" in block
        assert "body" in block
        assert "source_signals" in block
        assert isinstance(block["source_signals"], list)
