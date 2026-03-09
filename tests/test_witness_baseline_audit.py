"""
FILE: tests/test_witness_baseline_audit.py
VERSION: 0.1.0
PURPOSE:
Tests for the witness baseline audit (L4A).

BUILD MANIFEST: Stage 5 — Witness Baseline Audit.
"""

import pytest

from engine.analysis.witness_baseline_audit import (
    OBLIGATIONS,
    WitnessAuditResult,
    run_witness_audit,
)


# ── test fixtures ────────────────────────────────────────────────────

CLEAN_AP_ARTICLE = (
    "Officials confirmed Thursday that the new bridge construction "
    "project will begin in September. The transportation department "
    "reported that funding was approved last month. According to "
    "county records, the project will cost approximately $4.2 million. "
    "A spokesperson for the department said construction is expected "
    "to take 18 months. The mayor told reporters the project had "
    "broad community support. Council members noted that the budget "
    "was reviewed over three meetings."
)

SINGLE_SOURCE_ARTICLE = (
    "The mayor said the project will begin in September. "
    "The mayor said funding was approved last month. "
    "The mayor said the cost will be $4.2 million. "
    "The mayor said construction will take 18 months."
)

QUOTE_WITHOUT_ATTRIBUTION = (
    'The project timeline was set for September. '
    '"This is a major step forward for our community." '
    'The budget allocation was finalized at $4.2 million. '
    '"We expect construction to begin on schedule." '
    'The project has broad community support.'
)

EDITORIALIZING_ARTICLE = (
    "Officials confirmed the budget Thursday. According to the "
    "department, the project was approved. A spokesperson said the "
    "timeline was on track. The outcome was shameful and outrageous "
    "given the community's needs. Officials noted the vote was 5-2."
)

MISSING_ATTRIBUTION_ARTICLE = (
    "The project will cost $4.2 million. Construction is expected "
    "to take 18 months. The budget was approved last month. "
    "The timeline is on track. The community has broad support. "
    "The new bridge will transform the downtown area. "
    "Traffic congestion has been a problem for years."
)

UNLABELED_ALLEGATION_ARTICLE = (
    "Officials confirmed the budget Thursday. The opposition "
    "condemned the mayor for fiscal irresponsibility. Critics "
    "blamed the administration for cost overruns. Community "
    "leaders denounced the project as wasteful. A spokesperson "
    "said the project was on schedule."
)


# ── Clean AP-style reporting → pass ──────────────────────────────────

class TestCleanArticle:
    def test_clean_ap_returns_pass(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        assert result.status == "pass"

    def test_clean_ap_mode_audited(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        assert result.mode_audited == "witness"

    def test_clean_ap_all_checks_pass(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        for f in result.findings:
            assert f["passed"] is True, f"Check {f['check']} unexpectedly failed: {f['evidence']}"


# ── Single-source article → warn ─────────────────────────────────────

class TestSingleSource:
    def test_single_source_returns_warn(self):
        """Single attribution verb form ('said' only) triggers
        source_diversity warn. This is a shallow proxy for
        single-source dependency — it detects single-verb-form
        usage, not true speaker identity."""
        result = run_witness_audit(text=SINGLE_SOURCE_ARTICLE)
        assert result.status == "warn"

    def test_single_source_diversity_flagged(self):
        result = run_witness_audit(text=SINGLE_SOURCE_ARTICLE)
        diversity = _find(result, "source_diversity")
        assert diversity["passed"] is False


# ── Quote without attribution → warn ─────────────────────────────────

class TestQuoteWithoutAttribution:
    def test_unlinked_quote_returns_warn(self):
        result = run_witness_audit(text=QUOTE_WITHOUT_ATTRIBUTION)
        assert result.status in {"warn", "fail"}

    def test_quote_linkage_flagged(self):
        result = run_witness_audit(text=QUOTE_WITHOUT_ATTRIBUTION)
        linkage = _find(result, "quote_source_linkage")
        assert linkage["passed"] is False


# ── Editorializing language → warn ────────────────────────────────────

class TestEditorializing:
    def test_editorializing_triggers_warn(self):
        result = run_witness_audit(text=EDITORIALIZING_ARTICLE)
        assert result.status in {"warn", "fail"}

    def test_object_discipline_flagged(self):
        result = run_witness_audit(text=EDITORIALIZING_ARTICLE)
        discipline = _find(result, "object_discipline_check")
        assert discipline["passed"] is False
        assert "shameful" in discipline["evidence"].lower()


# ── Missing attribution → fail ────────────────────────────────────────

class TestMissingAttribution:
    def test_missing_attribution_returns_fail(self):
        result = run_witness_audit(text=MISSING_ATTRIBUTION_ARTICLE)
        assert result.status == "fail"

    def test_attribution_presence_flagged(self):
        result = run_witness_audit(text=MISSING_ATTRIBUTION_ARTICLE)
        attr = _find(result, "attribution_presence")
        assert attr["passed"] is False
        assert attr["severity"] == "fail"


# ── Unlabeled allegation → fail ───────────────────────────────────────

class TestUnlabeledAllegation:
    def test_unlabeled_allegation_returns_fail(self):
        result = run_witness_audit(text=UNLABELED_ALLEGATION_ARTICLE)
        assert result.status == "fail"

    def test_allegation_labeling_flagged(self):
        result = run_witness_audit(text=UNLABELED_ALLEGATION_ARTICLE)
        allege = _find(result, "allegation_labeling")
        assert allege["passed"] is False
        assert allege["severity"] == "fail"


# ── Non-witness mode → fail-closed ────────────────────────────────────

class TestFailClosed:
    def test_non_witness_returns_fail(self):
        result = run_witness_audit(
            text=CLEAN_AP_ARTICLE,
            presented_mode="argument",
        )
        assert result.status == "fail"

    def test_non_witness_notes_explain(self):
        result = run_witness_audit(
            text=CLEAN_AP_ARTICLE,
            presented_mode="argument",
        )
        assert result.notes == "Witness audit invoked on non-witness mode"

    def test_non_witness_no_findings(self):
        result = run_witness_audit(
            text=CLEAN_AP_ARTICLE,
            presented_mode="explanation",
        )
        assert result.findings == []

    def test_non_witness_zero_metrics(self):
        result = run_witness_audit(
            text=CLEAN_AP_ARTICLE,
            presented_mode="proof",
        )
        assert result.metrics["total_checks"] == 0


# ── Status aggregation ────────────────────────────────────────────────

class TestStatusAggregation:
    def test_fail_overrides_warn(self):
        """An article with both fail and warn conditions returns fail."""
        text = (
            "The policy is shameful and outrageous. "
            "The project will cost millions. Construction is underway. "
            "The timeline was set last year. The budget was finalized. "
            "The plan has broad implications for everyone."
        )
        result = run_witness_audit(text=text)
        assert result.status == "fail"

    def test_pass_requires_all_checks_pass(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        assert result.status == "pass"
        assert all(f["passed"] for f in result.findings)


# ── obligations_checked ───────────────────────────────────────────────

class TestObligationsChecked:
    def test_contains_all_7_checks(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        assert result.obligations_checked == OBLIGATIONS

    def test_obligations_static_on_fail_closed(self):
        result = run_witness_audit(
            text=CLEAN_AP_ARTICLE,
            presented_mode="argument",
        )
        assert result.obligations_checked == OBLIGATIONS

    def test_obligations_count(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        assert len(result.obligations_checked) == 7


# ── Metrics ───────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_keys_present(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        assert "total_checks" in result.metrics
        assert "passed_checks" in result.metrics
        assert "warned_checks" in result.metrics
        assert "failed_checks" in result.metrics

    def test_clean_article_metrics(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        assert result.metrics["total_checks"] == 7
        assert result.metrics["passed_checks"] == 7
        assert result.metrics["warned_checks"] == 0
        assert result.metrics["failed_checks"] == 0

    def test_metrics_sum_to_total(self):
        result = run_witness_audit(text=EDITORIALIZING_ARTICLE)
        total = (result.metrics["passed_checks"]
                 + result.metrics["warned_checks"]
                 + result.metrics["failed_checks"])
        assert total == result.metrics["total_checks"]


# ── Output contract ──────────────────────────────────────────────────

class TestOutputContract:
    def test_result_type(self):
        result = run_witness_audit(text="Some text here.")
        assert isinstance(result, WitnessAuditResult)

    def test_status_valid_values(self):
        for text in [CLEAN_AP_ARTICLE, EDITORIALIZING_ARTICLE,
                     MISSING_ATTRIBUTION_ARTICLE]:
            result = run_witness_audit(text=text)
            assert result.status in {"pass", "warn", "fail"}

    def test_findings_have_required_fields(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        for f in result.findings:
            assert "check" in f
            assert "passed" in f
            assert "severity" in f
            assert "evidence" in f

    def test_finding_severity_valid(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        for f in result.findings:
            assert f["severity"] in {"warn", "fail"}

    def test_exactly_one_finding_per_obligation(self):
        result = run_witness_audit(text=CLEAN_AP_ARTICLE)
        checks = [f["check"] for f in result.findings]
        assert checks == OBLIGATIONS


# ── helpers ──────────────────────────────────────────────────────────

def _find(result: WitnessAuditResult, check_name: str) -> dict:
    """Find a specific check in the findings list."""
    for f in result.findings:
        if f["check"] == check_name:
            return f
    raise KeyError(f"Check {check_name!r} not found in findings")
