BIASLENS / SURVIVOR — STAGE 4 LOGIC BLUEPRINT
MODULE: EEPlanner (L5B — Evaluation Planning)
VERSION: 0.1
STATUS: LOCKED
DATE: 2026-03-08

Companion to: ARCHITECTURE_BLUEPRINT_v0.2.md, BUILD_MANIFEST_v1.md

======================================================================
1. PURPOSE
======================================================================

The Evaluation Planner (L5B) translates the Escalation Decision (L5A)
and Mode Result (L2) into a structured EvaluationPlan — the "mission
brief" that downstream layers consume.

L5B answers one question:

    "What capabilities are authorized for this evaluation?"

L5B does not answer:

    "How much effort is needed?" (that is L5A)
    "Which specific AI calls to make?" (that is the future router)
    "What did the AI find?" (that is L6/L7)

L5B is a planner, not a router. It authorizes capabilities as strings,
not imports or function calls.

======================================================================
2. INPUTS
======================================================================

Required:
    mode_result: ModeResult
        Full object preserved per Rule 9B.

    escalation_decision: EscalationDecision
        From L5A. Contains level, trigger_reasons,
        offramp_permitted_by_policy.

======================================================================
3. OUTPUT: EvaluationPlan
======================================================================

Produced by: L5B
Consumed by: Future router, L6, L7, L8

Required fields (10):
    presented_mode: str
    escalation_level: str               none | reviewer | full
    offramp_permitted_by_policy: bool
    stop_early_allowed: bool
    authorized_baseline_audits: list[str]
    authorized_deep_modules: list[str]
    requires_functional_review: bool
    requires_full_arbitration: bool
    source_signals: list[dict]          Each entry: {layer, signal_name, weight}
    reasoning_summary: str

======================================================================
4. AUTHORIZATION MATRIX
======================================================================

----------------------------------------------------------------------
none
----------------------------------------------------------------------
authorized_baseline_audits: ["{mode}_baseline"]
authorized_deep_modules: []
requires_functional_review: false
requires_full_arbitration: false

Baseline only. No AI intervention.

----------------------------------------------------------------------
reviewer
----------------------------------------------------------------------
authorized_baseline_audits: ["{mode}_baseline"]
authorized_deep_modules: ["functional_mode_review"]
requires_functional_review: true
requires_full_arbitration: false

Single-model interpretive pass authorized.

----------------------------------------------------------------------
full
----------------------------------------------------------------------
authorized_baseline_audits: ["{mode}_baseline"]
authorized_deep_modules: ["functional_mode_review", "survivor_arbitration"]
requires_functional_review: true
requires_full_arbitration: true

Multi-model arbitration authorized.

======================================================================
5. TACTICAL RULES
======================================================================

----------------------------------------------------------------------
Rule A: Mode-specific baseline audit
----------------------------------------------------------------------
The baseline audit name is always "{presented_mode}_baseline".
A wrong-mode baseline audit must never be authorized.

----------------------------------------------------------------------
Rule B: Stop-early gate (two gates)
----------------------------------------------------------------------
stop_early_allowed is true only when BOTH conditions hold:
    1. offramp_permitted_by_policy is true (from L5A)
    2. escalation_level == "none"

This is the clean finding path. If either gate fails,
stop_early_allowed is false.

----------------------------------------------------------------------
Rule C: Escalation level passthrough
----------------------------------------------------------------------
The planner must NOT recalculate or modify the escalation level.
It passes through escalation_decision.level unchanged.

----------------------------------------------------------------------
Rule D: Source signals preservation
----------------------------------------------------------------------
source_signals must be a flat, traceable list of upstream
contributors. Each entry has the form:

    {"layer": str, "signal_name": str, "weight": float}

Sources are built only from Stage 4's actual inputs:

    - L2 (ModeResult): entries derived from ModeResult.signals
      using each signal's original name and weight.

    - L5A (EscalationDecision): entries derived from trigger_reasons
      with weight = 0.0, since these are traceability markers rather
      than scored signals.

Stage 4 does not directly consume L3 PersuasionResult.
L3 contributions are reflected indirectly through L5A trigger_reasons.

----------------------------------------------------------------------
Rule E: Reasoning summary
----------------------------------------------------------------------
reasoning_summary is a concise, human-readable string explaining
the plan. It must be populated (non-empty) for every plan.

======================================================================
6. CONSTRAINTS — WHAT L5B MUST NEVER DO
======================================================================

1. No policy recalculation.
   L5B does not re-evaluate escalation rules.

2. No execution routing.
   L5B does not call AI or import modules.

3. No AI dependency.
   L5B is a pure, deterministic function of its inputs.

4. No new doctrine logic.
   L5B applies the authorization matrix, nothing more.

5. No pipeline wiring.
   L5B does not import from or depend on pipeline.py.

======================================================================
7. STAGE 4 BUILD SCOPE
======================================================================

Stage 4 builds L5B as a standalone module.

Will build:
    engine/analysis/evaluation_planner.py
    tests/test_evaluation_planner.py

Will not build:
    Execution router (future)
    AI orchestration (future)
    Pipeline integration (future)

Stage 4 output must be testable in isolation.
Stage 4 must not import from or depend on pipeline.py.
Stage 4 must not modify any existing files.

======================================================================
END OF STAGE 4 LOGIC BLUEPRINT
======================================================================
