"""
FILE: tests/test_mode_normalizer.py
VERSION: 0.1.0
PURPOSE:
Tests for mode normalization / drift firewall.

BUILD MANIFEST: Stage 1 — Mode Spine.
"""

import pytest

from engine.analysis.mode_normalizer import normalize_mode


# ── alias resolution ──────────────────────────────────────────────────

class TestAliasResolution:
    def test_news_to_witness(self):
        result = normalize_mode("news")
        assert result.mode == "witness"
        assert result.peg_scope == "limited"

    def test_reporting_to_witness(self):
        result = normalize_mode("reporting")
        assert result.mode == "witness"

    def test_opinion_to_argument(self):
        result = normalize_mode("opinion")
        assert result.mode == "argument"
        assert result.peg_scope == "full"

    def test_editorial_to_argument(self):
        result = normalize_mode("editorial")
        assert result.mode == "argument"

    def test_research_to_proof(self):
        result = normalize_mode("research")
        assert result.mode == "proof"
        assert result.peg_scope == "standard"

    def test_legal_to_rule(self):
        result = normalize_mode("legal")
        assert result.mode == "rule"

    def test_analysis_to_explanation(self):
        result = normalize_mode("analysis")
        assert result.mode == "explanation"
        assert result.peg_scope == "full"

    def test_memoir_to_experience(self):
        result = normalize_mode("memoir")
        assert result.mode == "experience"
        assert result.peg_scope == "minimal"

    def test_encyclopedia_to_record(self):
        result = normalize_mode("encyclopedia")
        assert result.mode == "record"

    def test_press_release_to_voice(self):
        result = normalize_mode("press_release")
        assert result.mode == "voice"
        assert result.peg_scope == "full"

    def test_math_to_formal(self):
        result = normalize_mode("math")
        assert result.mode == "formal"
        assert result.peg_scope == "standard"


# ── canonical modes pass through ──────────────────────────────────────

class TestCanonicalPassthrough:
    def test_witness_passthrough(self):
        result = normalize_mode("witness")
        assert result.mode == "witness"

    def test_argument_passthrough(self):
        result = normalize_mode("argument")
        assert result.mode == "argument"

    def test_uncertain_passthrough(self):
        result = normalize_mode("uncertain")
        assert result.mode == "uncertain"
        assert result.is_uncertain is True


# ── fail-closed behavior ─────────────────────────────────────────────

class TestFailClosed:
    def test_unknown_string_to_uncertain(self):
        result = normalize_mode("weird_unknown_mode")
        assert result.mode == "uncertain"
        assert result.is_uncertain is True

    def test_none_to_uncertain(self):
        result = normalize_mode(None)
        assert result.mode == "uncertain"
        assert result.is_uncertain is True

    def test_empty_string_to_uncertain(self):
        result = normalize_mode("")
        assert result.mode == "uncertain"
        assert result.is_uncertain is True

    def test_whitespace_to_uncertain(self):
        result = normalize_mode("   ")
        assert result.mode == "uncertain"


# ── string cleaning ───────────────────────────────────────────────────

class TestStringCleaning:
    def test_uppercase_normalized(self):
        result = normalize_mode("WITNESS")
        assert result.mode == "witness"

    def test_mixed_case_normalized(self):
        result = normalize_mode("Argument")
        assert result.mode == "argument"

    def test_hyphens_normalized(self):
        result = normalize_mode("press-release")
        assert result.mode == "voice"

    def test_spaces_normalized(self):
        result = normalize_mode("press release")
        assert result.mode == "voice"

    def test_leading_trailing_whitespace(self):
        result = normalize_mode("  witness  ")
        assert result.mode == "witness"


# ── formal submode handling ───────────────────────────────────────────

class TestFormalSubmode:
    def test_formal_with_mathematics(self):
        result = normalize_mode("formal", "mathematics")
        assert result.mode == "formal"
        assert result.formal_submode == "mathematics"

    def test_formal_with_logic(self):
        result = normalize_mode("formal", "logic")
        assert result.mode == "formal"
        assert result.formal_submode == "logic"

    def test_formal_with_math_alias(self):
        result = normalize_mode("formal", "math")
        assert result.mode == "formal"
        assert result.formal_submode == "mathematics"

    def test_formal_with_none_submode(self):
        result = normalize_mode("formal", None)
        assert result.mode == "formal"
        assert result.formal_submode == "none"

    def test_formal_with_unknown_submode(self):
        result = normalize_mode("formal", "topology")
        assert result.mode == "formal"
        assert result.formal_submode == "none"

    def test_non_formal_ignores_submode(self):
        result = normalize_mode("witness", "mathematics")
        assert result.mode == "witness"
        assert result.formal_submode == "none"


# ── PEG scope correctness ────────────────────────────────────────────

class TestPegScope:
    @pytest.mark.parametrize("mode,expected_scope", [
        ("witness", "limited"),
        ("proof", "standard"),
        ("rule", "limited"),
        ("explanation", "full"),
        ("argument", "full"),
        ("experience", "minimal"),
        ("record", "limited"),
        ("voice", "full"),
        ("formal", "standard"),
        ("uncertain", "limited"),
    ])
    def test_peg_scope_per_mode(self, mode, expected_scope):
        result = normalize_mode(mode)
        assert result.peg_scope == expected_scope
