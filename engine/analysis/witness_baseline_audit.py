"""
FILE: engine/analysis/witness_baseline_audit.py
VERSION: 0.1.0
PURPOSE:
Witness Baseline Audit (L4A) for the Epistemic Evaluation Engine.

Deterministic structural audit that verifies reporting-style articles
satisfy the structural obligations of witness journalism.

Checks reporting discipline only. Does not verify truth, infer bias,
infer intent, detect omissions, or call AI.

CONSTRAINTS:
- Deterministic only. No AI.
- Surface structural heuristics only.
- A PASS means no structural reporting violations detected,
  not that the article is true.

BLUEPRINT: ARCHITECTURE_BLUEPRINT_v0.2 — Layer L4A.
LOGIC BLUEPRINT: STAGE5_LOGIC_BLUEPRINT.md
BUILD MANIFEST: Stage 5 — Witness Baseline Audit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── constants ────────────────────────────────────────────────────────

OBLIGATIONS = [
    "attribution_presence",
    "allegation_labeling",
    "quote_source_linkage",
    "source_diversity",
    "fact_claim_separation",
    "narrative_inflation",
    "object_discipline_check",
]

_FAIL_CONDITIONS = {
    "attribution_presence",
    "allegation_labeling",
}

_WARN_CONDITIONS = {
    "quote_source_linkage",
    "source_diversity",
    "fact_claim_separation",
    "narrative_inflation",
    "object_discipline_check",
}

_SEVERITY_MAP = {
    name: "fail" if name in _FAIL_CONDITIONS else "warn"
    for name in OBLIGATIONS
}


# ── attribution patterns ─────────────────────────────────────────────

_ATTRIBUTION_PATTERNS = re.compile(
    r'\b(?:said|says|according to|told|stated|reported|confirmed|'
    r'announced|added|explained|noted|wrote|testified)\b',
    re.IGNORECASE,
)

_QUOTE_PATTERN = re.compile(r'["\u201c\u201d]')

_ACCUSATION_VERBS = re.compile(
    r'\b(?:accused|blamed|condemned|denounced|attacked|slammed|'
    r'ripped|blasted|lashed out at)\b',
    re.IGNORECASE,
)

_CLAIM_VERBS = re.compile(
    r'\b(?:is|are|was|were|will be|has been|have been|causes|leads to|'
    r'results in|proves|shows that|demonstrates|means)\b',
    re.IGNORECASE,
)

_GENERALIZATION_MARKERS = re.compile(
    r'\b(?:all|entire|every|systemic|society|widespread|always|'
    r'never|nobody|everybody|universal|total|across the board)\b',
    re.IGNORECASE,
)

_EVALUATIVE_ADJECTIVES = re.compile(
    r'\b(?:shameful|heroic|outrageous|disgraceful|unconscionable|'
    r'appalling|devastating|brilliant|courageous|despicable|'
    r'deplorable|magnificent|glorious|atrocious|reprehensible)\b',
    re.IGNORECASE,
)


# ── data types ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class WitnessAuditResult:
    """Output of the witness baseline audit (L4A)."""
    mode_audited: str
    status: str                                    # pass | warn | fail
    obligations_checked: list[str] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    notes: str = ""


# ── public API ───────────────────────────────────────────────────────

def run_witness_audit(
    text: str,
    title: Optional[str] = None,
    presented_mode: str = "witness",
) -> WitnessAuditResult:
    """Run the witness baseline audit on the given text.

    Args:
        text:            Raw body text of the article.
        title:           Optional article title.
        presented_mode:  Must be "witness" or audit fails closed.

    Returns:
        WitnessAuditResult with status, findings, and metrics.
    """
    # ── Fail-closed rule ────────────────────────────────────────
    if presented_mode != "witness":
        return WitnessAuditResult(
            mode_audited="witness",
            status="fail",
            obligations_checked=list(OBLIGATIONS),
            findings=[],
            metrics={"total_checks": 0, "passed_checks": 0,
                     "warned_checks": 0, "failed_checks": 0},
            notes="Witness audit invoked on non-witness mode",
        )

    # ── Run all detectors ───────────────────────────────────────
    combined = text
    if title:
        combined = title + " " + text

    findings: list[dict] = []
    for check_name in OBLIGATIONS:
        detector = _DETECTORS[check_name]
        passed, evidence = detector(combined, text, title)
        findings.append({
            "check": check_name,
            "passed": passed,
            "severity": _SEVERITY_MAP[check_name],
            "evidence": evidence,
        })

    # ── Status aggregation ──────────────────────────────────────
    status = _aggregate_status(findings)

    # ── Metrics ─────────────────────────────────────────────────
    passed_count = sum(1 for f in findings if f["passed"])
    failed_count = sum(1 for f in findings
                       if not f["passed"] and f["severity"] == "fail")
    warned_count = sum(1 for f in findings
                       if not f["passed"] and f["severity"] == "warn")

    metrics = {
        "total_checks": len(findings),
        "passed_checks": passed_count,
        "warned_checks": warned_count,
        "failed_checks": failed_count,
    }

    return WitnessAuditResult(
        mode_audited="witness",
        status=status,
        obligations_checked=list(OBLIGATIONS),
        findings=findings,
        metrics=metrics,
        notes="",
    )


# ── status aggregation ──────────────────────────────────────────────

def _aggregate_status(findings: list[dict]) -> str:
    """Determine overall status from findings."""
    for f in findings:
        if not f["passed"] and f["severity"] == "fail":
            return "fail"
    for f in findings:
        if not f["passed"] and f["severity"] == "warn":
            return "warn"
    return "pass"


# ── detectors ────────────────────────────────────────────────────────
# Each detector returns (passed: bool, evidence: str).
# Parameters: combined (title+text), text (body only), title.

def _check_attribution_presence(
    combined: str, text: str, title: Optional[str],
) -> tuple[bool, str]:
    """Check that claim-like sentences have attribution."""
    sentences = _split_sentences(text)
    if not sentences:
        return True, "No sentences to check."

    claim_sentences = [s for s in sentences if _CLAIM_VERBS.search(s)]
    if not claim_sentences:
        return True, "No claim-bearing sentences found."

    unattributed = [
        s for s in claim_sentences
        if not _ATTRIBUTION_PATTERNS.search(s)
    ]

    if not unattributed:
        return True, f"All {len(claim_sentences)} claim-bearing sentences have attribution."

    ratio = len(unattributed) / len(claim_sentences)
    if ratio > 0.5:
        return (
            False,
            f"{len(unattributed)} of {len(claim_sentences)} claim-bearing "
            f"sentences lack attribution.",
        )

    return True, f"{len(unattributed)} of {len(claim_sentences)} claim-bearing sentences lack attribution (within tolerance)."


def _check_allegation_labeling(
    combined: str, text: str, title: Optional[str],
) -> tuple[bool, str]:
    """Check that accusation language has attribution framing."""
    sentences = _split_sentences(text)
    accusation_sentences = [
        s for s in sentences if _ACCUSATION_VERBS.search(s)
    ]
    if not accusation_sentences:
        return True, "No accusation language found."

    unlabeled = [
        s for s in accusation_sentences
        if not _ATTRIBUTION_PATTERNS.search(s)
    ]

    if not unlabeled:
        return True, f"All {len(accusation_sentences)} accusation sentences have attribution."

    return (
        False,
        f"{len(unlabeled)} of {len(accusation_sentences)} accusation "
        f"sentences lack attribution framing.",
    )


def _check_quote_source_linkage(
    combined: str, text: str, title: Optional[str],
) -> tuple[bool, str]:
    """Check that quoted material appears near attribution tokens."""
    sentences = _split_sentences(text)
    quote_sentences = [s for s in sentences if _QUOTE_PATTERN.search(s)]
    if not quote_sentences:
        return True, "No quoted material found."

    unlinked = [
        s for s in quote_sentences
        if not _ATTRIBUTION_PATTERNS.search(s)
    ]

    if not unlinked:
        return True, f"All {len(quote_sentences)} quoted passages have source linkage."

    return (
        False,
        f"{len(unlinked)} of {len(quote_sentences)} quoted passages "
        f"lack nearby attribution.",
    )


def _check_source_diversity(
    combined: str, text: str, title: Optional[str],
) -> tuple[bool, str]:
    """Check for multiple distinct attribution phrases.

    Note: This is a shallow heuristic that counts distinct attribution
    verb forms (e.g., "said", "told", "according to"), not distinct
    named speakers. It detects single-verb-form dependency as a proxy
    for single-source dependency.
    """
    matches = _ATTRIBUTION_PATTERNS.findall(text)
    if not matches:
        return True, "No attribution phrases found (nothing to assess)."

    distinct = set(m.lower().strip() for m in matches)
    if len(distinct) >= 2:
        return True, f"{len(distinct)} distinct attribution phrases found."

    return (
        False,
        f"Only {len(distinct)} distinct attribution phrase found; "
        f"possible single-source dependency.",
    )


def _check_fact_claim_separation(
    combined: str, text: str, title: Optional[str],
) -> tuple[bool, str]:
    """Check that strong causal/proof claims have attribution."""
    sentences = _split_sentences(text)
    if not sentences:
        return True, "No sentences to check."

    strong_claims = [
        s for s in sentences
        if re.search(r'\b(?:proves|demonstrates|shows that|causes|'
                     r'leads to|results in)\b', s, re.IGNORECASE)
    ]

    if not strong_claims:
        return True, "No strong causal/proof claims found."

    unattributed_claims = [
        s for s in strong_claims
        if not _ATTRIBUTION_PATTERNS.search(s)
    ]

    if not unattributed_claims:
        return True, f"All {len(strong_claims)} strong claims have attribution."

    return (
        False,
        f"{len(unattributed_claims)} of {len(strong_claims)} strong "
        f"claims lack attribution (fact/claim boundary unclear).",
    )


def _check_narrative_inflation(
    combined: str, text: str, title: Optional[str],
) -> tuple[bool, str]:
    """Check for generalization markers that inflate narrative scope."""
    matches = _GENERALIZATION_MARKERS.findall(combined)
    if len(matches) < 3:
        return True, f"{len(matches)} generalization marker(s) found (within tolerance)."

    return (
        False,
        f"{len(matches)} generalization markers found: "
        f"{', '.join(sorted(set(m.lower() for m in matches)))}.",
    )


def _check_object_discipline(
    combined: str, text: str, title: Optional[str],
) -> tuple[bool, str]:
    """Check for evaluative language inconsistent with witness discipline."""
    matches = _EVALUATIVE_ADJECTIVES.findall(combined)
    if not matches:
        return True, "No evaluative adjectives detected."

    return (
        False,
        f"{len(matches)} evaluative adjective(s) found: "
        f"{', '.join(sorted(set(m.lower() for m in matches)))}.",
    )


# ── detector registry ────────────────────────────────────────────────

_DETECTORS = {
    "attribution_presence": _check_attribution_presence,
    "allegation_labeling": _check_allegation_labeling,
    "quote_source_linkage": _check_quote_source_linkage,
    "source_diversity": _check_source_diversity,
    "fact_claim_separation": _check_fact_claim_separation,
    "narrative_inflation": _check_narrative_inflation,
    "object_discipline_check": _check_object_discipline,
}


# ── helpers ──────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Split text into sentences (simple heuristic)."""
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 10]
