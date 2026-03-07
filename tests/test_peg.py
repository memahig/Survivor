"""Tests for engine.analysis.peg — PEG profile builder."""

from engine.analysis.peg import build_peg_profile, _determine_level, _join_mechanisms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _block(mechanism: str) -> dict:
    return {"mechanism": mechanism, "title": "t", "body": "b", "source_signals": []}


def _enriched(mechanisms=None, fragility="unknown"):
    """Build minimal enriched substrate for PEG testing."""
    blocks = [_block(m) for m in (mechanisms or [])]
    return {
        "reader_interpretation": {
            "mechanism_blocks": blocks,
            "block_count": len(blocks),
            "bottom_line_plain": "test",
        },
        "load_bearing": {
            "argument_fragility": fragility,
        },
    }


# ---------------------------------------------------------------------------
# _join_mechanisms grammar
# ---------------------------------------------------------------------------

class TestJoinMechanisms:
    def test_empty(self):
        assert _join_mechanisms([]) == "structural mechanisms"

    def test_one(self):
        assert _join_mechanisms(["A"]) == "A"

    def test_two(self):
        assert _join_mechanisms(["A", "B"]) == "A and B"

    def test_three(self):
        assert _join_mechanisms(["A", "B", "C"]) == "A, B, and C"

    def test_four(self):
        assert _join_mechanisms(["A", "B", "C", "D"]) == "A, B, C, and D"


# ---------------------------------------------------------------------------
# Unavailable / degraded input
# ---------------------------------------------------------------------------

class TestUnavailable:
    def test_none_input(self):
        result = build_peg_profile(None)
        assert result["peg_level"] == "unknown"
        assert "unavailable" in result["peg_line"].lower()

    def test_empty_dict(self):
        result = build_peg_profile({})
        assert result["peg_level"] == "unknown"

    def test_reader_interpretation_error(self):
        enriched = {"reader_interpretation": {"error": "boom"}}
        result = build_peg_profile(enriched)
        assert result["peg_level"] == "unknown"
        assert "unavailable" in result["peg_line"].lower()

    def test_reader_interpretation_missing(self):
        enriched = {"load_bearing": {"argument_fragility": "high"}}
        result = build_peg_profile(enriched)
        assert result["peg_level"] == "unknown"


# ---------------------------------------------------------------------------
# Minimal — no mechanisms
# ---------------------------------------------------------------------------

class TestMinimal:
    def test_no_mechanisms(self):
        result = build_peg_profile(_enriched([]))
        assert result["peg_level"] == "minimal"
        assert result["mechanism_count"] == 0
        assert result["core_count"] == 0
        assert result["tilt_active"] is False
        assert result["fragility_sensitivity"] is False

    def test_minimal_peg_line(self):
        result = build_peg_profile(_enriched([]))
        assert "no significant" in result["peg_line"].lower()


# ---------------------------------------------------------------------------
# Notable — 1 core mechanism
# ---------------------------------------------------------------------------

class TestNotable:
    def test_one_core(self):
        result = build_peg_profile(_enriched(["omission_dependence"]))
        assert result["peg_level"] == "notable"
        assert result["core_count"] == 1

    def test_notable_peg_line(self):
        result = build_peg_profile(_enriched(["unsupported_causal"]))
        assert "includes some elements sometimes used in propaganda-style persuasion" in result["peg_line"]

    def test_notable_does_not_overclaim(self):
        result = build_peg_profile(_enriched(["omission_dependence"]))
        assert result["peg_level"] == "notable"
        assert "heavily relies" not in result["peg_line"]
        assert "relies on several" not in result["peg_line"]

    def test_secondary_only_no_fragility(self):
        result = build_peg_profile(_enriched(["official_reliance", "baseline_absence"]))
        assert result["peg_level"] == "minimal"

    def test_secondary_with_high_fragility(self):
        result = build_peg_profile(
            _enriched(["official_reliance", "baseline_absence"], fragility="high")
        )
        assert result["peg_level"] == "notable"


# ---------------------------------------------------------------------------
# Severe
# ---------------------------------------------------------------------------

class TestSevere:
    def test_two_core_with_tilt(self):
        result = build_peg_profile(
            _enriched(["omission_dependence", "load_bearing_weakness"])
        )
        assert result["peg_level"] == "severe"
        assert result["tilt_active"] is True

    def test_two_core_with_high_fragility(self):
        result = build_peg_profile(
            _enriched(["omission_dependence", "unsupported_causal"], fragility="high")
        )
        assert result["peg_level"] == "severe"

    def test_three_core_no_tilt_no_fragility(self):
        result = build_peg_profile(
            _enriched(["omission_dependence", "unsupported_causal", "scope_inflation"])
        )
        assert result["peg_level"] == "severe"

    def test_severe_peg_line(self):
        result = build_peg_profile(
            _enriched(["omission_dependence", "load_bearing_weakness"])
        )
        assert "relies on several elements often used in propaganda-style persuasion" in result["peg_line"]
        assert "increase persuasive force beyond what the evidence fully supports" in result["peg_line"]

    def test_severe_line_uses_relies_on(self):
        result = build_peg_profile(
            _enriched(["omission_dependence", "unsupported_causal"], fragility="high")
        )
        assert result["peg_level"] == "severe"
        assert "This argument relies on" in result["peg_line"]


# ---------------------------------------------------------------------------
# Critical
# ---------------------------------------------------------------------------

class TestCritical:
    def test_three_core_with_tilt(self):
        result = build_peg_profile(
            _enriched([
                "omission_dependence", "unsupported_causal", "load_bearing_weakness"
            ], fragility="high")
        )
        assert result["peg_level"] == "critical"
        assert result["tilt_active"] is True

    def test_three_core_with_fragility_sensitivity(self):
        result = build_peg_profile(
            _enriched([
                "omission_dependence", "framing_escalation", "scope_inflation"
            ], fragility="high")
        )
        assert result["peg_level"] == "critical"
        assert result["fragility_sensitivity"] is True

    def test_critical_peg_line(self):
        result = build_peg_profile(
            _enriched([
                "omission_dependence", "unsupported_causal", "load_bearing_weakness"
            ], fragility="high")
        )
        assert "heavily relies on elements commonly used in propaganda-style persuasion" in result["peg_line"]
        assert "depends more on persuasive structure than on fully demonstrated evidence" in result["peg_line"]
        assert "omitted rival explanations" in result["peg_line"]

    def test_critical_line_max_3_mechanisms(self):
        result = build_peg_profile(
            _enriched([
                "omission_dependence", "unsupported_causal",
                "load_bearing_weakness", "framing_escalation", "scope_inflation"
            ], fragility="high")
        )
        line = result["peg_line"]
        assert "omitted rival explanations" in line
        assert "unsupported causal claims" in line
        assert "load-bearing weakness" in line
        assert "escalating framing" not in line
        assert "scope inflation" not in line


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_mechanisms(self):
        enriched = {
            "reader_interpretation": {
                "mechanism_blocks": [
                    _block("omission_dependence"),
                    _block("omission_dependence"),
                    _block("unsupported_causal"),
                ],
                "block_count": 3,
                "bottom_line_plain": "test",
            },
            "load_bearing": {"argument_fragility": "unknown"},
        }
        result = build_peg_profile(enriched)
        assert result["mechanism_count"] == 2
        assert result["active_mechanisms"] == ["omission_dependence", "unsupported_causal"]


# ---------------------------------------------------------------------------
# Core vs secondary counting
# ---------------------------------------------------------------------------

class TestCoreSecondary:
    def test_mixed_counts(self):
        result = build_peg_profile(
            _enriched(["omission_dependence", "official_reliance", "baseline_absence"])
        )
        assert result["core_count"] == 1
        assert result["secondary_count"] == 2
        assert result["mechanism_count"] == 3
        assert result["peg_level"] == "notable"


# ---------------------------------------------------------------------------
# _determine_level direct tests
# ---------------------------------------------------------------------------

class TestDetermineLevel:
    def test_minimal(self):
        assert _determine_level(
            core_count=0, secondary_count=0,
            tilt_active=False, fragility_sensitivity=False, high_fragility=False,
        ) == "minimal"

    def test_notable_one_core(self):
        assert _determine_level(
            core_count=1, secondary_count=0,
            tilt_active=False, fragility_sensitivity=False, high_fragility=False,
        ) == "notable"

    def test_severe_two_core_tilt(self):
        assert _determine_level(
            core_count=2, secondary_count=0,
            tilt_active=True, fragility_sensitivity=False, high_fragility=False,
        ) == "severe"

    def test_critical_three_core_tilt(self):
        assert _determine_level(
            core_count=3, secondary_count=0,
            tilt_active=True, fragility_sensitivity=False, high_fragility=False,
        ) == "critical"

    def test_critical_three_core_fragility_sensitivity(self):
        assert _determine_level(
            core_count=3, secondary_count=0,
            tilt_active=False, fragility_sensitivity=True, high_fragility=True,
        ) == "critical"

    def test_three_core_no_tilt_no_frag_is_severe(self):
        assert _determine_level(
            core_count=3, secondary_count=0,
            tilt_active=False, fragility_sensitivity=False, high_fragility=False,
        ) == "severe"
