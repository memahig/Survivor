BIASLENS / SURVIVOR — STAGE 5 LOGIC BLUEPRINT
MODULE: Witness Baseline Audit (L4A)
VERSION: 0.1
STATUS: LOCKED
DATE: 2026-03-09

Companion to: ARCHITECTURE_BLUEPRINT_v0.2.md, BUILD_MANIFEST_v1.md

======================================================================
1. PURPOSE
======================================================================

The Witness Baseline Audit (L4A) is the first mode-specific baseline
audit in the Evaluation Engine.

It verifies that a reporting-style article satisfies the structural
obligations of witness journalism.

L4A answers one question:

    "Does this article meet the structural discipline expected
     of witness-mode reporting?"

L4A does not answer:

    "Is the article true?" (requires verification)
    "Is the article biased?" (requires interpretive analysis)
    "What is the author's intent?" (requires inference)
    "What is omitted?" (requires domain knowledge)

L4A checks reporting discipline only.

======================================================================
2. INPUTS
======================================================================

Required:
    text: str               Raw body text of the article.

Optional:
    title: str | None       Article title.
    presented_mode: str     Must be "witness" or audit fails closed.

The audit does not require EvaluationPlan as an input.
The planner authorizes the audit; the audit is independently testable.

======================================================================
3. OUTPUT: WitnessAuditResult
======================================================================

Produced by: L4A
Consumed by: Clean-path gate, L8 (report composition)

Required fields:
    mode_audited: str
    status: str                 pass | warn | fail
    obligations_checked: list[str]
    findings: list[dict]
    metrics: dict[str, int]
    notes: str

Each finding must contain:
    check: str
    passed: bool
    severity: str               warn | fail
    evidence: str

======================================================================
4. OBLIGATIONS CHECKED (STATIC LIST)
======================================================================

The obligations_checked field must always equal:

    attribution_presence
    allegation_labeling
    quote_source_linkage
    source_diversity
    fact_claim_separation
    narrative_inflation
    object_discipline_check

This list is static. Do not generate dynamically.
Exactly one finding per obligation.

======================================================================
5. FAIL / WARN CLASSIFICATION
======================================================================

----------------------------------------------------------------------
Fail conditions
----------------------------------------------------------------------
    attribution_presence
    allegation_labeling

----------------------------------------------------------------------
Warn conditions
----------------------------------------------------------------------
    quote_source_linkage
    source_diversity
    fact_claim_separation
    narrative_inflation
    object_discipline_check

======================================================================
6. STATUS AGGREGATION
======================================================================

    fail → any FAIL condition fails
    warn → any WARN condition fails (and no FAILs)
    pass → all checks pass

======================================================================
7. METRICS
======================================================================

metrics must contain:

    total_checks: int
    passed_checks: int
    warned_checks: int
    failed_checks: int

Counts must be derived from findings.

======================================================================
8. CANONICAL CHECKS
======================================================================

----------------------------------------------------------------------
attribution_presence (FAIL)
----------------------------------------------------------------------
Missing attribution in claim-bearing sentences.
Fires when >50% of claim-bearing sentences lack attribution verbs.

----------------------------------------------------------------------
allegation_labeling (FAIL)
----------------------------------------------------------------------
Accusation language without attribution framing.
Fires when accusation verbs appear without nearby attribution.

----------------------------------------------------------------------
quote_source_linkage (WARN)
----------------------------------------------------------------------
Quoted material without source linkage.
Fires when quoted passages lack attribution in the same sentence.

----------------------------------------------------------------------
source_diversity (WARN)
----------------------------------------------------------------------
Single-source dependency proxy.
Fires when only one distinct attribution phrase form is used.
Note: This is a shallow heuristic that counts distinct attribution
verb forms, not distinct named speakers.

----------------------------------------------------------------------
fact_claim_separation (WARN)
----------------------------------------------------------------------
Strong causal/proof claims without attribution.
Fires when proves/demonstrates/causes/etc. appear without attribution.

----------------------------------------------------------------------
narrative_inflation (WARN)
----------------------------------------------------------------------
Generalization markers that inflate narrative scope.
Fires when 3+ generalization markers appear (all, entire, every,
systemic, widespread, always, never, etc.).

----------------------------------------------------------------------
object_discipline_check (WARN)
----------------------------------------------------------------------
Evaluative language inconsistent with witness discipline.
Fires when evaluative adjectives appear (shameful, heroic,
outrageous, disgraceful, etc.).
Distinct from L3 persuasion heat — this checks mode discipline.

======================================================================
9. CLEAN-PATH INTERACTION
======================================================================

This module does NOT decide early exit.

Pipeline rule:

    Early clean exit requires:
        EvaluationPlan.stop_early_allowed == True
        AND WitnessAuditResult.status == "pass"

    Warn or Fail must block clean exit.

======================================================================
10. FAIL-CLOSED RULE
======================================================================

If presented_mode != "witness":

    Return status = "fail"
    Return notes = "Witness audit invoked on non-witness mode"
    Do not run detectors.

======================================================================
11. CONSTRAINTS — WHAT L4A MUST NEVER DO
======================================================================

1. No truth verification.
2. No bias inference.
3. No intent inference.
4. No omission detection.
5. No AI or LLM calls.
6. No external APIs.
7. No deep NLP models.
8. No political bias judgment.

Stage 5 detectors are surface-level structural checks, not deep
semantic analysis. A pass means no structural reporting red flags
were detected, not that the article is verified or bias-free.

======================================================================
12. STAGE 5 BUILD SCOPE
======================================================================

Stage 5 builds L4A as a standalone module.

Will build:
    engine/analysis/witness_baseline_audit.py
    tests/test_witness_baseline_audit.py

Will not build:
    Other mode audits (future stages)
    Pipeline integration (future)
    L8 report rendering of audit results (future)

Stage 5 output must be testable in isolation.
Stage 5 must not import from or depend on pipeline.py.
Stage 5 must not modify any existing files.

======================================================================
END OF STAGE 5 LOGIC BLUEPRINT
======================================================================
