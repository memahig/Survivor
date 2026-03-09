BIASLENS / SURVIVOR — BUILD MANIFEST
VERSION: 1.0
STATUS: PRE-BUILD LOCK PACKET
DATE: 2026-03-08

Companion to: ARCHITECTURE_BLUEPRINT_v0.2.md

======================================================================
PART 1: LAYER-TO-CODEBASE MAPPING
======================================================================

What exists, what stays, what's new.

----------------------------------------------------------------------
L0 — Structural Ingest
----------------------------------------------------------------------

EXISTS:
    engine/core/ingest.py         — URL/file ingestion, stable article ID
    engine/core/evidence_bank.py  — deterministic chunking into E1..En

NEEDS MODIFICATION:
    ingest.py        — title field exists but never populated
    evidence_bank.py — flat line chunker, no slot awareness

BLOCKED BY:
    Slot-aware evidence bank redesign (pipeline-killing duplicate quote crash)

----------------------------------------------------------------------
L1 — Normalization
----------------------------------------------------------------------

EXISTS:
    engine/core/normalize.py      — text cleanup, whitespace normalization
    engine/core/validators.py     — 8-layer drift firewall (normalize_reviewer_pack)

NEEDS MODIFICATION:
    validators.py — add Layer 9 (mode string normalization) when mode
                     data starts flowing from reviewers

----------------------------------------------------------------------
L2 — Presented Mode Classification
----------------------------------------------------------------------

EXISTS (PARTIAL):
    engine/eo/genre_alignment.py  — GSAE-specific, NOT doctrine-aligned

NEW (Stage 1):
    engine/core/mode_constants.py — 9 modes, PEG scope, aliases
    engine/core/mode_types.py     — data contracts (ModeResult, NormalizedMode, etc.)
    engine/analysis/mode_classifier.py  — deterministic presented-mode classifier
    engine/analysis/mode_normalizer.py  — string canonicalization

----------------------------------------------------------------------
L3 — Universal Persuasion Screen
----------------------------------------------------------------------

EXISTS (DEEP, not cheap):
    engine/analysis/peg.py                  — PEG profile builder (v1.0 locked)
    engine/analysis/reader_interpretation.py — 7 mechanism detectors

NEW (Stage 2):
    engine/analysis/persuasion_screen.py — cheap regex/statistical heat scan

NOTE: PEG and reader_interpretation are L6-depth modules. The universal
persuasion screen (L3) must be a NEW lightweight layer that runs before
AI. Existing modules remain in L6 for escalated cases.

----------------------------------------------------------------------
L4 — Mode-Specific Baseline Audit
----------------------------------------------------------------------

EXISTS (can inform L4 design):
    engine/analysis/baseline_context_detector.py — stats without baselines
    engine/analysis/causal_inference_detector.py  — unsupported causal claims

NEW (Stage 4):
    engine/analysis/witness_audit.py    — attribution, causal restraint
    engine/analysis/proof_audit.py      — data-to-claim proportionality
    engine/analysis/argument_audit.py   — structural persuasion discipline
    (additional mode audits as needed)

NOTE: Existing baseline_context_detector and causal_inference_detector
are currently wired into substrate_enricher (L6). They may be partially
migrated into L4 if they can run cheaply without full reviewer output.

----------------------------------------------------------------------
L5A/B — Escalation Policy + Evaluation Router
----------------------------------------------------------------------

EXISTS (implicit):
    engine/core/pipeline.py — currently runs everything unconditionally

NEW (Stage 3):
    engine/analysis/escalation_policy.py  — determines none/reviewer/full
    engine/analysis/evaluation_router.py  — activates modules per decision

NOTE: pipeline.py currently has no escalation concept. All articles get
full Phase 1 + Phase 2 + adjudication + enrichment. The router will
eventually gate this.

----------------------------------------------------------------------
L6 — Single-Model Interpretive Evaluation
----------------------------------------------------------------------

EXISTS:
    engine/reviewers/openai_reviewer.py   — OpenAI adapter (gpt-4o-mini)
    engine/reviewers/gemini_reviewer.py   — Gemini adapter (gemini-2.5-flash)
    engine/reviewers/claude_reviewer.py   — Claude adapter (claude-sonnet-4-6)
    engine/reviewers/mock_reviewer.py     — mock for testing
    engine/reviewers/base.py              — reviewer protocol
    engine/reviewers/errors.py            — shared error classification
    engine/analysis/substrate_enricher.py — orchestrates 9 analysis modules

9 EXISTING ANALYSIS MODULES (all L6):
    causal_inference_detector
    baseline_context_detector
    official_assertion_detector
    claim_deduplicator
    load_bearing_claims
    omission_ranker
    reads_like_label
    signal_prioritizer
    reader_interpretation

NEEDS MODIFICATION (Stage 5+):
    Phase 1 prompts — add epistemic_mode to reviewer output schema
    substrate_enricher — receive mode context, apply PEG scope gating

----------------------------------------------------------------------
L7 — Multi-Model Arbitration (Survivor)
----------------------------------------------------------------------

EXISTS:
    engine/core/adjudicator.py     — LEGACY, still wired to pipeline
    engine/arena/judge.py          — MODERN, production-ready, NOT wired
    engine/core/voting.py          — equivalence group + tally (shared)
    engine/core/divergence_radar.py — post-adjudication divergence analysis
    engine/core/spine_builder.py   — cross-reviewer argument spine

KNOWN GAP:
    pipeline.py v0.5 calls legacy adjudicator, not judge.py
    This is a pre-existing issue, not blocked by this build

----------------------------------------------------------------------
L8 — Synthesis / Report Composition
----------------------------------------------------------------------

EXISTS:
    engine/render/blunt_report.py  — forensic storytelling (v2.1)
    engine/render/audit_report.py  — full forensic audit
    engine/render/blunt_bundle.py  — wrapper (md, json, error)

NEEDS (Stage 7):
    Clean finding report template
    Mode-aware report sections

----------------------------------------------------------------------
L9 — Cross-Article / Corpus (BiasLens+)
----------------------------------------------------------------------

NOT STARTED. Future scope.

======================================================================
PART 2: BUILD STAGES
======================================================================

----------------------------------------------------------------------
Stage 1: Mode Spine (no pipeline changes)
----------------------------------------------------------------------

Files:
    engine/core/mode_constants.py
    engine/core/mode_types.py
    engine/analysis/mode_classifier.py
    engine/analysis/mode_normalizer.py
    tests/test_mode_classifier.py
    tests/test_mode_normalizer.py

Tests prove:
    - All 9 modes + uncertain classified correctly on canonical fixtures
    - Aliases normalize to canonical modes
    - Unknown strings fail closed to uncertain
    - Formal submodes detected
    - Confidence thresholds produce correct labels

Dependencies: none
Pipeline impact: none
Commit: standalone

----------------------------------------------------------------------
Stage 2: Universal Persuasion Screen
----------------------------------------------------------------------

Files:
    engine/analysis/persuasion_screen.py
    tests/test_persuasion_screen.py

Tests prove:
    - Clean text returns low heat
    - Loaded text returns high heat
    - Heat score is deterministic
    - No false positives on neutral witness reporting

Dependencies: Stage 1 (mode context informs interpretation)
Pipeline impact: none yet (standalone module)
Commit: standalone

Note: Stage 2 output (PersuasionResult) must be consumable by the
future EvaluationPlan (Blueprint Rule 9A), not only by a direct router.

----------------------------------------------------------------------
Stage 3: Escalation Router
----------------------------------------------------------------------

Files:
    engine/analysis/escalation_policy.py
    engine/analysis/evaluation_router.py
    tests/test_escalation_policy.py
    tests/test_evaluation_router.py

Tests prove:
    - Uncertain mode always escalates to reviewer minimum
    - Low heat + passing audit = escalation none
    - High heat = escalation reviewer or full
    - Router activates correct modules per decision

Dependencies: Stages 1 + 2
Pipeline impact: none yet (standalone)
Commit: standalone

Note: Stage 3 must produce a structured EvaluationPlan before execution
routing occurs (Blueprint Rule 9A — Routing Plan Rule).

----------------------------------------------------------------------
Stage 4: Mode-Specific Baseline Audits
----------------------------------------------------------------------

Files:
    engine/analysis/witness_audit.py
    engine/analysis/argument_audit.py
    (additional audits per mode as needed)
    tests/test_witness_audit.py
    tests/test_argument_audit.py

Tests prove:
    - Witness audit passes clean attribution-rich text
    - Witness audit warns on causal inflation
    - Argument audit detects directional persuasion structure
    - Each audit respects mode-specific obligations

Dependencies: Stages 1-3
Pipeline impact: none yet
Commit: standalone

----------------------------------------------------------------------
Stage 5: Pipeline Integration
----------------------------------------------------------------------

Changes:
    engine/prompts/survivor_boot.txt — doctrine preamble
    engine/reviewers/base.py — epistemic_mode in Phase 1 schema
    engine/core/validators.py — Layer 9 mode normalizer
    engine/core/pipeline.py — insert L2-L5 before Phase 1

Tests prove:
    - Pipeline runs with mode classification pre-step
    - Reviewers emit epistemic_mode in Phase 1 output
    - Mode normalizer catches alias drift
    - Existing 686 tests still pass

Dependencies: Stages 1-4
Pipeline impact: YES — first integration point
Commit: careful, incremental

----------------------------------------------------------------------
Stage 6: Survivor Arbitration Refinement
----------------------------------------------------------------------

Changes:
    - Mode adjudication (presented vs functional)
    - Camouflage detection from mode gap
    - PEG scope gating per adjudicated mode

Dependencies: Stage 5
Pipeline impact: yes

----------------------------------------------------------------------
Stage 7: Report Refinement
----------------------------------------------------------------------

Changes:
    - Clean finding report template
    - Mode-aware report sections
    - Validation badge concept

Dependencies: Stage 6

----------------------------------------------------------------------
Stage 8: BiasLens+ (Future)
----------------------------------------------------------------------

Cross-article corpus comparison. Not scoped yet.

======================================================================
PART 3: CANONICAL DATA OBJECTS
======================================================================

These are the main data objects that flow between layers.

----------------------------------------------------------------------
ModeResult (L2 output)
----------------------------------------------------------------------
    presented_mode: str       (one of 9 modes + uncertain)
    confidence: float         (0.0-1.0)
    confidence_label: str     (low/medium/high)
    formal_submode: str       (logic/mathematics/none)
    signals: list             (name, weight, evidence)
    requires_reviewer_confirm: bool

----------------------------------------------------------------------
NormalizedMode (L2 -> downstream)
----------------------------------------------------------------------
    mode: str                 (canonical mode name)
    formal_submode: str
    peg_scope: str            (full/standard/limited/minimal)
    is_uncertain: bool

----------------------------------------------------------------------
PersuasionResult (L3 output)
----------------------------------------------------------------------
    heat_level: str           (low/moderate/high)
    score: float
    signals: list             (name, weight, evidence)
    escalation_recommendation: str

----------------------------------------------------------------------
AuditResult (L4 output)
----------------------------------------------------------------------
    mode: str
    findings: list            (check_name, status, evidence, severity)
    escalation: EscalationDecision or null
    summary: str

----------------------------------------------------------------------
EscalationDecision (L5A output)
----------------------------------------------------------------------
    level: str                (none/reviewer/full)
    score: float
    triggers: list            (name, severity, evidence)
    rationale: str

----------------------------------------------------------------------
EvaluationPlan (L5 output — Blueprint Rule 9A)
----------------------------------------------------------------------
    presented_mode: str
    mode_confidence: float
    is_clean_candidate: bool
    escalation_level: str     (none/reviewer/full)
    stop_early_allowed: bool
    allowed_baseline_audits: list
    allowed_deep_modules: list
    requires_functional_mode_review: bool
    requires_full_arbitration: bool

----------------------------------------------------------------------
CleanFinding (L8 output, escalation=none)
----------------------------------------------------------------------
    escalation_level: str     (none)
    finding: str              (clean)
    presented_mode: str
    confidence: float
    summary: str              ("This object meets its epistemic obligations
                                for [mode]-mode discourse.")

======================================================================
PART 4: WHAT IS DELIBERATELY NOT BUILT YET
======================================================================

1. Slot-aware evidence bank (L0 fix — parallel track, unblocks pipeline)
2. Headline-body concordance engine (requires slot-aware evidence)
3. Functional mode detection by reviewers (Stage 5+)
4. Mode camouflage warning synthesis (Stage 6)
5. Counterfactual reversal stress test (Layer 4 of Canonical Spec)
6. Cross-article corpus comparison (BiasLens+)
7. Full PEG formula reconciliation (doctrine v1.0 numeric vs v1.1 mechanism)
8. Shared transport/retry abstraction (provider parity debt)

======================================================================
END OF BUILD MANIFEST
======================================================================
