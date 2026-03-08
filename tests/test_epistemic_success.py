"""Tests for engine.analysis.epistemic_success — ESM profile builder."""

from engine.analysis.epistemic_success import (
    build_success_profile,
    _determine_success_level,
    _join_labels,
    _extract_valid_successes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sblock(mechanism: str) -> dict:
    return {"mechanism": mechanism}


def _enriched(success_mechanisms=None, classification="general"):
    """Build minimal enriched substrate for ESM testing."""
    blocks = [_sblock(m) for m in (success_mechanisms or [])]
    return {
        "reader_interpretation": {
            "mechanism_blocks": [],
            "success_blocks": blocks,
            "block_count": 0,
            "bottom_line_plain": "test",
        },
        "adjudicated_whole_article_judgment": {
            "classification": classification,
        },
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# _join_labels grammar
# ---------------------------------------------------------------------------

class TestJoinLabels:
    def test_empty(self):
        assert _join_labels([]) == "integrity-strengthening mechanisms"

    def test_one(self):
        assert _join_labels(["A"]) == "A"

    def test_two(self):
        assert _join_labels(["A", "B"]) == "A and B"

    def test_three(self):
        assert _join_labels(["A", "B", "C"]) == "A, B, and C"


# ---------------------------------------------------------------------------
# Unavailable / degraded input
# ---------------------------------------------------------------------------

class TestUnavailable:
    def test_none_input(self):
        result = build_success_profile(None)
        assert result["success_level"] == "unknown"
        assert "unavailable" in result["integrity_line"].lower()

    def test_empty_dict(self):
        # Empty dict has no reader_interpretation error, so ESM runs and finds nothing
        result = build_success_profile({})
        assert result["success_level"] == "minimal"

    def test_reader_interpretation_error(self):
        enriched = {"reader_interpretation": {"error": "boom"}}
        result = build_success_profile(enriched)
        assert result["success_level"] == "unknown"

    def test_reader_interpretation_missing(self):
        # Missing reader_interpretation (no error key) → runs with empty blocks → minimal
        enriched = {"metadata": {"object_type": "journalism"}}
        result = build_success_profile(enriched)
        assert result["success_level"] == "minimal"


# ---------------------------------------------------------------------------
# Minimal — no success signals
# ---------------------------------------------------------------------------

class TestMinimal:
    def test_no_success_blocks(self):
        result = build_success_profile(_enriched([]))
        assert result["success_level"] == "minimal"
        assert result["deep_rigor_count"] == 0
        assert result["structural_rigor_count"] == 0
        assert result["active_successes"] == []

    def test_minimal_integrity_line(self):
        result = build_success_profile(_enriched([]))
        assert "no distinct" in result["integrity_line"].lower()

    def test_unknown_mechanism_ignored(self):
        result = build_success_profile(_enriched(["made_up_signal"]))
        assert result["success_level"] == "minimal"
        assert result["active_successes"] == []


# ---------------------------------------------------------------------------
# Notable — structural rigor only
# ---------------------------------------------------------------------------

class TestNotable:
    def test_one_structural(self):
        result = build_success_profile(_enriched(["proportional_hedging"]))
        assert result["success_level"] == "notable"
        assert result["structural_rigor_count"] == 1
        assert result["deep_rigor_count"] == 0

    def test_two_structural(self):
        result = build_success_profile(_enriched([
            "proportional_hedging", "scope_discipline"
        ]))
        assert result["success_level"] == "notable"
        assert result["structural_rigor_count"] == 2

    def test_notable_integrity_line(self):
        result = build_success_profile(_enriched(["causal_transparency"]))
        assert "notable" in result["integrity_line"].lower()


# ---------------------------------------------------------------------------
# High — deep >= 1 or structural >= 3
# ---------------------------------------------------------------------------

class TestHigh:
    def test_one_deep(self):
        result = build_success_profile(_enriched(["adverse_fact_inclusion"]))
        assert result["success_level"] == "high"
        assert result["deep_rigor_count"] == 1

    def test_three_structural(self):
        result = build_success_profile(_enriched([
            "proportional_hedging", "causal_transparency", "scope_discipline"
        ]))
        assert result["success_level"] == "high"
        assert result["structural_rigor_count"] == 3

    def test_high_integrity_line(self):
        result = build_success_profile(_enriched(["steel_manning"]))
        assert "significant" in result["integrity_line"].lower()


# ---------------------------------------------------------------------------
# Exceptional — deep >= 2 and structural >= 2
# ---------------------------------------------------------------------------

class TestExceptional:
    def test_two_deep_two_structural(self):
        result = build_success_profile(_enriched([
            "adverse_fact_inclusion", "steel_manning",
            "proportional_hedging", "scope_discipline",
        ]))
        assert result["success_level"] == "exceptional"
        assert result["deep_rigor_count"] == 2
        assert result["structural_rigor_count"] == 2

    def test_exceptional_integrity_line(self):
        result = build_success_profile(_enriched([
            "adverse_fact_inclusion", "uncertainty_visibility",
            "causal_transparency", "comparative_grounding",
        ]))
        assert "exceptional" in result["integrity_line"].lower()
        assert "recoverability" in result["integrity_line"].lower()


# ---------------------------------------------------------------------------
# _determine_success_level direct tests
# ---------------------------------------------------------------------------

class TestDetermineLevel:
    def test_minimal(self):
        assert _determine_success_level(0, 0) == "minimal"

    def test_notable(self):
        assert _determine_success_level(0, 1) == "notable"
        assert _determine_success_level(0, 2) == "notable"

    def test_high_deep(self):
        assert _determine_success_level(1, 0) == "high"
        assert _determine_success_level(1, 1) == "high"

    def test_high_structural(self):
        assert _determine_success_level(0, 3) == "high"

    def test_exceptional(self):
        assert _determine_success_level(2, 2) == "exceptional"
        assert _determine_success_level(3, 3) == "exceptional"


# ---------------------------------------------------------------------------
# Extraction / deduplication
# ---------------------------------------------------------------------------

class TestExtraction:
    def test_dedup(self):
        blocks = [_sblock("steel_manning"), _sblock("steel_manning")]
        result = _extract_valid_successes(blocks)
        assert result == ["steel_manning"]

    def test_order_preserved(self):
        blocks = [
            _sblock("scope_discipline"),
            _sblock("adverse_fact_inclusion"),
        ]
        result = _extract_valid_successes(blocks)
        assert result == ["scope_discipline", "adverse_fact_inclusion"]

    def test_unknown_filtered(self):
        blocks = [_sblock("fake"), _sblock("proportional_hedging")]
        result = _extract_valid_successes(blocks)
        assert result == ["proportional_hedging"]

    def test_non_dict_ignored(self):
        result = _extract_valid_successes(["not_a_dict", 42])
        assert result == []


# ---------------------------------------------------------------------------
# Domain routing
# ---------------------------------------------------------------------------

class TestDomainRouting:
    def test_journalism_domain_hits(self):
        enriched = _enriched(
            ["adverse_fact_inclusion", "uncertainty_visibility"],
            classification="journalism",
        )
        result = build_success_profile(enriched)
        assert result["domain_alignment"] == "journalism"
        assert "adverse_fact_inclusion" in result["domain_priority_hits"]
        assert "uncertainty_visibility" in result["domain_priority_hits"]

    def test_advocacy_domain_hits(self):
        enriched = _enriched(
            ["steel_manning", "comparative_grounding"],
            classification="advocacy",
        )
        result = build_success_profile(enriched)
        assert result["domain_alignment"] == "advocacy"
        assert "steel_manning" in result["domain_priority_hits"]

    def test_unknown_classification_defaults_general(self):
        enriched = _enriched(["proportional_hedging"], classification="")
        result = build_success_profile(enriched)
        assert result["domain_alignment"] == "general"
        assert result["domain_priority_hits"] == []

    def test_metadata_object_type_takes_precedence(self):
        enriched = _enriched(
            ["adverse_fact_inclusion"],
            classification="advocacy",
        )
        enriched["metadata"] = {"object_type": "journalism"}
        result = build_success_profile(enriched)
        assert result["domain_alignment"] == "journalism"

    def test_fallback_to_classification_when_no_metadata(self):
        enriched = _enriched(
            ["steel_manning"],
            classification="advocacy",
        )
        enriched["metadata"] = {}
        result = build_success_profile(enriched)
        assert result["domain_alignment"] == "advocacy"


# ---------------------------------------------------------------------------
# Non-compensability (ESM does not affect PEG)
# ---------------------------------------------------------------------------

class TestNonCompensability:
    def test_esm_output_shape_is_independent(self):
        """ESM output has no PEG keys — they cannot interact."""
        result = build_success_profile(_enriched([
            "adverse_fact_inclusion", "steel_manning",
            "proportional_hedging", "scope_discipline",
        ]))
        assert "peg_level" not in result
        assert "peg_line" not in result
        assert result["success_level"] == "exceptional"
