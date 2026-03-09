"""
FILE: tests/test_persuasion_screen.py
VERSION: 0.1.0
PURPOSE:
Tests for the universal persuasion screen (L3).

BUILD MANIFEST: Stage 2 — Universal Persuasion Screen.
"""

import pytest

from engine.analysis.persuasion_screen import (
    PersuasionResult,
    scan_persuasion,
)


# ── canonical fixture: clean AP/Reuters-style ────────────────────────

class TestCleanFixture:
    def test_clean_wire_report_low_heat(self):
        text = """
        Officials confirmed Thursday that the new bridge construction
        project will begin in September. The transportation department
        reported that funding was approved last month. According to
        county records, the project will cost approximately $4.2 million.
        A spokesperson for the department said construction is expected
        to take 18 months.
        """
        result = scan_persuasion(text=text, title="Bridge project approved")
        assert result.heat_level == "low"
        assert result.is_clean_candidate is True

    def test_clean_wire_report_no_signals(self):
        text = """
        The city council voted Tuesday to approve the annual budget.
        Council members reviewed the proposal over three meetings.
        The budget allocates funds for road maintenance, public safety,
        and parks. The vote was 5-2 in favor.
        """
        result = scan_persuasion(text=text)
        assert result.heat_level == "low"
        assert result.detector_count == 0

    def test_clean_research_abstract(self):
        text = """
        This study examines the relationship between soil pH and crop
        yield in temperate regions. Data were collected from 120 farms
        over a three-year period. Results indicate a moderate positive
        correlation between soil acidity and wheat production. Further
        research is needed to establish causal mechanisms.
        """
        result = scan_persuasion(text=text, title="Soil pH and crop yield")
        assert result.heat_level == "low"
        assert result.is_clean_candidate is True


# ── canonical fixture: Halevi stress case ────────────────────────────

class TestHaleviStressFixture:
    def test_halevi_high_heat(self):
        text = """
        This is nothing less than an existential threat to our democracy.
        Without question, the policy is a shameful betrayal of everything
        we stand for. Experts agree that we must act immediately — the
        collapse of our institutions is not a distant possibility but an
        imminent certainty. Everyone knows this cannot continue. It is
        essential that we reject this unconscionable assault on our values
        before it is too late. The only way forward is total resistance.
        """
        result = scan_persuasion(text=text, title="The crisis demands action")
        assert result.heat_level == "high"
        assert result.is_clean_candidate is False

    def test_halevi_multiple_families(self):
        text = """
        This is nothing less than an existential threat to our democracy.
        Without question, the policy is a shameful betrayal of everything
        we stand for. Experts agree that we must act immediately — the
        collapse of our institutions is not a distant possibility but an
        imminent certainty. Everyone knows this cannot continue. It is
        essential that we reject this unconscionable assault on our values
        before it is too late. The only way forward is total resistance.
        """
        result = scan_persuasion(text=text)
        assert result.detector_count >= 3

    def test_halevi_signals_have_family(self):
        text = """
        This is nothing less than an existential threat to our democracy.
        Without question, the policy is a shameful betrayal of everything
        we stand for. Experts agree that we must act immediately — the
        collapse of our institutions is not a distant possibility but an
        imminent certainty. Everyone knows this cannot continue. It is
        essential that we reject this unconscionable assault on our values
        before it is too late. The only way forward is total resistance.
        """
        result = scan_persuasion(text=text)
        for signal in result.signals:
            assert signal.family != ""
            assert signal.name != ""


# ── moderate heat case ───────────────────────────────────────────────

class TestModerateHeat:
    def test_moderate_heat_not_clean_candidate(self):
        text = """
        Without question, the current approach is failing. It is certain
        that we cannot afford to ignore this any longer. We must demand
        accountability from those responsible. It is essential that reform
        begins now.
        """
        result = scan_persuasion(text=text)
        assert result.heat_level == "moderate"
        assert result.is_clean_candidate is False


# ── mode_result input contract ───────────────────────────────────────

class TestModeResultInput:
    def test_accepts_mode_result(self):
        from engine.core.mode_types import ModeResult
        mode_result = ModeResult(
            presented_mode="witness",
            confidence=0.85,
            confidence_label="high",
            formal_submode="none",
            signals=[],
            requires_reviewer_confirm=False,
            notes=None,
        )
        result = scan_persuasion(
            text="Officials confirmed the report Thursday.",
            mode_result=mode_result,
        )
        assert isinstance(result, PersuasionResult)
        assert result.heat_level in {"low", "moderate", "high"}


# ── title contribution ───────────────────────────────────────────────

class TestTitleContribution:
    def test_loaded_title_contributes_signal(self):
        neutral_body = """
        The committee met to review the proposal. Members discussed
        the timeline and budget. No major objections were raised.
        """
        result_no_title = scan_persuasion(text=neutral_body, title="")
        result_with_title = scan_persuasion(
            text=neutral_body,
            title="Without question a shameful and unconscionable betrayal",
        )
        assert result_with_title.heat_score >= result_no_title.heat_score


# ── detector family: certainty escalation ────────────────────────────

class TestCertaintyEscalation:
    def test_certainty_markers_fire(self):
        text = """
        Without question this is the most important issue of our time.
        It is certain that the current path leads to failure. Beyond
        doubt, the evidence is irrefutable.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "certainty_escalation" in families

    def test_single_certainty_marker_does_not_fire(self):
        text = """
        The results are undeniably interesting but require further
        investigation before conclusions can be drawn.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "certainty_escalation" not in families


# ── detector family: moral loading ───────────────────────────────────

class TestMoralLoading:
    def test_moral_markers_fire(self):
        text = """
        This is a shameful display of institutional failure. The
        unconscionable decision reflects a moral failing at every level.
        It is disgraceful that leaders allowed this to happen.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "moral_loading" in families

    def test_neutral_text_no_moral_loading(self):
        text = """
        The committee reviewed the proposal and identified several
        areas for improvement. Members suggested revisions to the
        timeline and budget allocation.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "moral_loading" not in families


# ── detector family: existential framing ─────────────────────────────

class TestExistentialFraming:
    def test_existential_markers_fire(self):
        text = """
        This represents an existential threat to the nation. We are
        at the brink of catastrophic failure that could lead to the
        collapse of everything we have built. Future generations will
        judge us for our inaction.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "existential_framing" in families

    def test_mild_future_reference_does_not_fire(self):
        text = """
        The project timeline extends into the next fiscal year.
        Planning for future phases will begin in January.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "existential_framing" not in families


# ── detector family: authority substitution ──────────────────────────

class TestAuthoritySubstitution:
    def test_authority_markers_fire(self):
        text = """
        Experts agree that this approach is fundamentally flawed.
        Leading authorities have concluded the same. The science is
        clear and research proves the danger beyond any doubt.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "authority_substitution" in families

    def test_specific_citation_does_not_fire(self):
        text = """
        According to a 2024 study published in Nature by Dr. Smith
        and colleagues at MIT, the correlation between temperature
        and precipitation was significant at p < 0.01.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "authority_substitution" not in families


# ── detector family: directional persuasion ──────────────────────────

class TestDirectionalPersuasion:
    def test_directional_markers_fire(self):
        text = """
        We must reject this proposal immediately. It is essential that
        citizens demand action from their representatives. We cannot
        afford to wait any longer. The time to act is now.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "directional_persuasion" in families

    def test_neutral_recommendation_does_not_fire(self):
        text = """
        The report recommends that the agency consider updating its
        guidelines to reflect current best practices. The review
        committee will meet next month to discuss options.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "directional_persuasion" not in families


# ── detector family: universalization ────────────────────────────────

class TestUniversalization:
    def test_universalization_markers_fire(self):
        text = """
        Everyone knows this policy has failed. No one disputes the
        evidence. Any reasonable person can see that the approach
        is universally accepted as flawed.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "universalization" in families

    def test_specific_claim_does_not_fire(self):
        text = """
        A survey of 500 residents found that 62 percent supported
        the proposal while 31 percent opposed it. The remaining
        7 percent expressed no opinion.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "universalization" not in families


# ── detector family: tonal drift ─────────────────────────────────────

class TestTonalDrift:
    def test_tonal_drift_on_escalating_text(self):
        text = (
            "The committee met on Thursday to review the annual budget. "
            "Members discussed revenue projections and spending priorities. "
            "The finance director presented quarterly results showing "
            "moderate growth across all sectors. Staff recommended minor "
            "adjustments to the capital improvement plan. "
            # second half escalates
            "But the reality is far more appalling than these dry numbers "
            "suggest. The situation is unconscionable and devastating. "
            "What we are witnessing is nothing short of catastrophic "
            "mismanagement. This is outrageous, shocking, and alarming. "
            "The devastation is appalling and unconscionable beyond words."
        )
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "tonal_drift" in families

    def test_no_tonal_drift_on_uniform_text(self):
        text = """
        The city council approved the budget on a 5-2 vote. The mayor
        expressed satisfaction with the outcome. Opposition members
        said they would continue to advocate for additional funding
        for public transportation. The next council meeting is
        scheduled for March 15. Members will review the capital
        improvement plan at that time.
        """
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "tonal_drift" not in families

    def test_short_text_skips_tonal_drift(self):
        text = "Short text."
        result = scan_persuasion(text=text)
        families = {s.family for s in result.signals}
        assert "tonal_drift" not in families


# ── empty and edge cases ─────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_text_returns_low(self):
        result = scan_persuasion(text="", title="")
        assert result.heat_level == "low"
        assert result.is_clean_candidate is True
        assert result.detector_count == 0

    def test_short_text_returns_low(self):
        result = scan_persuasion(text="A short paragraph with no signals.")
        assert result.heat_level == "low"
        assert result.is_clean_candidate is True

    def test_title_only_scanned(self):
        result = scan_persuasion(
            text="Neutral content about the weather.",
            title="Without question the most shameful betrayal",
        )
        # Title alone shouldn't have enough repeated markers to fire
        assert result.heat_level == "low"


# ── output contract ──────────────────────────────────────────────────

class TestOutputContract:
    def test_heat_level_valid_values(self):
        result = scan_persuasion(text="Nothing special here.")
        assert result.heat_level in {"low", "moderate", "high"}

    def test_heat_score_non_negative(self):
        result = scan_persuasion(text="Any text at all.")
        assert result.heat_score >= 0.0

    def test_detector_count_matches_families(self):
        text = """
        This is nothing less than an existential threat to our democracy.
        Without question, the policy is a shameful betrayal of everything
        we stand for. Experts agree that we must act immediately — the
        collapse of our institutions is not a distant possibility but an
        imminent certainty. Everyone knows this cannot continue. It is
        essential that we reject this unconscionable assault on our values
        before it is too late. The only way forward is total resistance.
        """
        result = scan_persuasion(text=text)
        unique_families = {s.family for s in result.signals}
        assert result.detector_count == len(unique_families)

    def test_is_clean_candidate_false_when_high_heat(self):
        text = """
        Without question this is undeniably the most shameful and
        unconscionable betrayal. Experts agree and scientists say
        this is an existential threat. Everyone knows we must act.
        It is essential and the only way forward. The collapse of
        our institutions is before it is too late.
        """
        result = scan_persuasion(text=text)
        if result.heat_level == "high":
            assert result.is_clean_candidate is False

    def test_result_is_persuasion_result_type(self):
        result = scan_persuasion(text="test")
        assert isinstance(result, PersuasionResult)

    def test_signals_have_required_fields(self):
        text = """
        Without question this is undeniably true. It is certain beyond
        doubt that the irrefutable evidence proves everything.
        """
        result = scan_persuasion(text=text)
        for signal in result.signals:
            assert hasattr(signal, "name")
            assert hasattr(signal, "weight")
            assert hasattr(signal, "evidence")
            assert hasattr(signal, "family")
