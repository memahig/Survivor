BIASLENS / SURVIVOR — STAGE 3 LOGIC BLUEPRINT
MODULE: EEPolicy (L5A — Escalation Policy)
VERSION: 0.1
STATUS: LOCKED
DATE: 2026-03-08

Companion to: ARCHITECTURE_BLUEPRINT_v0.2.md, BUILD_MANIFEST_v1.md

======================================================================
1. PURPOSE
======================================================================

The Escalation Policy (L5A) is the primary economic and epistemic
governor of the EEEngine. It translates the deterministic findings
from L2 (Mode) and L3 (Scanner) into a definitive Escalation Level.

This level sets the upper boundary for AI usage and structural
analysis depth.

L5A answers one question:

    "How much evaluation effort does this object require?"

L5A does not answer:

    "Which modules should run?" (that is the planner/router)
    "What did the AI find?" (that is L6/L7)
    "Is this object clean?" (that requires L4 baseline audit)

L5A is a governor, not an executor.

======================================================================
2. INPUTS
======================================================================

Required:
    mode_result: ModeResult
        Specifically: presented_mode, confidence_label,
        requires_reviewer_confirm.

    persuasion_result: PersuasionResult
        Specifically: heat_level, is_clean_candidate.

Future (optional, not required for Stage 3):
    audit_result: AuditResult
        When L4 baseline audits exist, policy may consume
        duties_satisfied to refine escalation.

======================================================================
3. OUTPUT: EscalationDecision
======================================================================

Produced by: L5A
Consumed by: L5 planner/router (future), L8 (report composition)

Required fields:
    level: str                      none | reviewer | full
    trigger_reasons: list[str]      All fired policy rules
    offramp_permitted_by_policy: bool

level is the decision-grade field.
trigger_reasons preserves all fired rules for traceability.
offramp_permitted_by_policy indicates if the clean finding path
is permitted at the policy level.

======================================================================
4. ESCALATION LEVELS
======================================================================

none
    Baseline only. No AI intervention.
    Authorized for the clean finding off-ramp.

reviewer
    Moderate concern or ambiguity.
    Authorized for a single-model interpretive pass (L6).

full
    High risk or complexity.
    Authorized for multi-model arbitration (L7/Survivor).
    Reserved for severe or compounded concern profiles at the
    policy layer.

======================================================================
5. PRECEDENCE RULE (LOCKED)
======================================================================

Ordering: none < reviewer < full

If multiple policy rules fire, the final EscalationDecision.level
must be the highest escalation level triggered by any applicable rule.

All fired trigger_reasons are preserved regardless of which rule
determined the final level.

======================================================================
6. POLICY MATRIX
======================================================================

----------------------------------------------------------------------
Rule 1: Uncertain mode override
----------------------------------------------------------------------
Condition: presented_mode == "uncertain"
Level: at least reviewer
Reason: "uncertain_mode"

Epistemic ambiguity requires AI to identify the object.

----------------------------------------------------------------------
Rule 2: High heat override
----------------------------------------------------------------------
Condition: heat_level == "high"
Level: at least reviewer
Reason: "high_heat"

Persuasive heat necessitates an interpretive check for camouflage.

----------------------------------------------------------------------
Rule 3: Clean path eligibility
----------------------------------------------------------------------
Condition: confidence_label == "high" AND heat_level == "low"
         AND is_clean_candidate == true
Level: none
Reason: (no trigger — this is the off-ramp path)

High integrity, low risk. Eligible for the off-ramp.

----------------------------------------------------------------------
Rule 4: Low confidence + moderate heat
----------------------------------------------------------------------
Condition: confidence_label == "low" AND heat_level == "moderate"
Level: reviewer
Reason: "low_confidence_moderate_heat"

Ambiguity plus moderate persuasive concern requires interpretive
review, but does not automatically justify full arbitration.

----------------------------------------------------------------------
Rule 5: Scanner contradiction override
----------------------------------------------------------------------
Condition: heat_level == "low" AND is_clean_candidate == false
Level: at least reviewer
Reason: "scanner_contradiction"

Scanner flagged a contradiction (e.g., tonal drift) despite
low overall heat score.

----------------------------------------------------------------------
Rule 6: Reviewer confirmation required
----------------------------------------------------------------------
Condition: requires_reviewer_confirm == true
Level: at least reviewer
Reason: "reviewer_confirm_required"

L2 classifier flagged insufficient confidence for deterministic
classification alone.

----------------------------------------------------------------------
Rule 7: Low confidence + high heat
----------------------------------------------------------------------
Condition: confidence_label == "low" AND heat_level == "high"
Level: full
Reason: "low_confidence_high_heat"

Maximum ambiguity with maximum persuasion signals.

======================================================================
7. OFF-RAMP RULE
======================================================================

offramp_permitted_by_policy is true only when:

    1. level == "none"
    2. No policy rule fired that would block early termination

The off-ramp means the object may proceed to L4 baseline audit
and, if L4 passes, terminate with a clean finding.

offramp_permitted_by_policy does NOT mean the object is clean.
The final clean finding requires L4 confirmation.

======================================================================
8. CONSTRAINTS — WHAT L5A MUST NEVER DO
======================================================================

1. No module lists.
   L5A does not decide which specific audit modules run.

2. No execution routing.
   L5A does not know how to call an AI. It only authorizes
   the intensity level.

3. No AI dependency.
   L5A is a pure, deterministic function of its inputs.

4. No quality verdict.
   L5A does not decide if an article is good or bad, only how
   much effort is required to evaluate it.

5. No motive inference.
   L5A does not guess why an object has high heat.

======================================================================
9. WHAT L5A CANNOT KNOW
======================================================================

- Functional mode (requires L6 interpretive analysis)
- Whether claims are supported (requires claim extraction)
- Whether omissions are significant (requires domain knowledge)
- Final quality of the object (requires full evaluation)

L5A sees only the L2 mode classification and L3 scanner output.
It governs intensity. It does not investigate.

======================================================================
10. STAGE 3 BUILD SCOPE
======================================================================

Stage 3 builds L5A as a standalone module.

Will build:
    engine/analysis/escalation_policy.py
    tests/test_escalation_policy.py

Will not build:
    Evaluation router (future)
    EvaluationPlan construction (future)
    Module authorization lists (future)
    L4 baseline audit integration (future)

Stage 3 output must be testable in isolation.
Stage 3 must not import from or depend on pipeline.py.
Stage 3 must not modify any existing files.

Future L4 audit_result input should be accepted as an optional
parameter from the start, but must not be required.

======================================================================
END OF STAGE 3 LOGIC BLUEPRINT
======================================================================
