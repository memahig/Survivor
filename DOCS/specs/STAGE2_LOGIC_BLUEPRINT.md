BIASLENS / SURVIVOR — STAGE 2 LOGIC BLUEPRINT
MODULE: EEScanner (L3 — Universal Persuasion Screen)
VERSION: 0.1
STATUS: LOCKED
DATE: 2026-03-08

Companion to: ARCHITECTURE_BLUEPRINT_v0.2.md, BUILD_MANIFEST_v1.md

======================================================================
1. PURPOSE
======================================================================

EEScanner is the universal persuasion screen (L3) of the Evaluation Engine.

Every object passes through L3 regardless of mode. Its job is cheap,
deterministic detection of persuasive structural signals in raw text.

L3 answers one question:

    "Does this text show surface-level persuasive heat?"

L3 does not answer:

    "Is this text persuasive?" (that is L6)
    "Is persuasion exceeding evidence?" (that is PEG)
    "What is this text trying to do?" (that is functional mode)

L3 is a smoke detector, not an investigator.

======================================================================
2. INPUTS
======================================================================

Required:
    text: str           Raw body text of the object.

Optional:
    title: str          Object title (used for signal detection).
    mode_result: ModeResult
                        Full Stage 1 output (Blueprint Rule 9B).
                        Used for mode-aware signal weighting,
                        not for filtering or skipping detection.

L3 must function without mode_result. If absent, all detectors run
with default weights.

======================================================================
3. OUTPUT: PersuasionResult
======================================================================

Produced by: L3
Consumed by: L5 (EvaluationPlan construction), L8 (report composition)

Required fields:
    heat_level: str         low | moderate | high
    heat_score: float       Aggregate weighted score (for debugging/tuning)
    signals: list           Each: {name, weight, evidence, family}
    is_clean_candidate: bool
    detector_count: int     Number of detector families that fired

heat_level is the decision-grade field. heat_score is diagnostic only.
Downstream consumers must use heat_level, not heat_score, for branching.

======================================================================
4. DETECTOR FAMILIES
======================================================================

Each family targets a distinct category of persuasive surface signal.
Families are listed here by category. Individual patterns remain flexible
and are not locked by this blueprint.

----------------------------------------------------------------------
4.1 Certainty Escalation
----------------------------------------------------------------------
Detects language that inflates confidence beyond what evidence supports.

Markers: absolute qualifiers, false-precision phrases, hedging removal.

Example surface signals:
    "without question", "undeniably", "the fact is", "it is certain"

----------------------------------------------------------------------
4.2 Moral Loading
----------------------------------------------------------------------
Detects ethical/moral framing injected into factual or analytical context.

Markers: moral vocabulary in non-ethical discourse, virtue/vice framing.

Example surface signals:
    "shameful", "heroic", "unconscionable", "duty to"

----------------------------------------------------------------------
4.3 Existential Framing
----------------------------------------------------------------------
Detects language that escalates stakes to survival/catastrophe level.

Markers: existential vocabulary, civilizational stakes, irreversibility.

Example surface signals:
    "existential threat", "point of no return", "survival of",
    "collapse of", "future generations"

----------------------------------------------------------------------
4.4 Authority Substitution
----------------------------------------------------------------------
Detects appeals to authority used in place of evidence.

Markers: credential-as-proof, expert consensus without data reference.

Example surface signals:
    "experts agree", "scientists say", "studies show" (without citation)

----------------------------------------------------------------------
4.5 Directional Persuasion
----------------------------------------------------------------------
Detects normative pressure toward a specific conclusion.

Markers: imperative framing, urgency language, call-to-action structure.

Example surface signals:
    "we must", "it is essential", "the only way", "should immediately"

Note: Overlap with Stage 1 argument detection is expected. L3 detects
surface markers for heat scoring. L2 detects them for mode classification.
The same evidence may serve both purposes at different weights.

----------------------------------------------------------------------
4.6 Universalization
----------------------------------------------------------------------
Detects language that treats selected examples as universal truths.

Markers: scope inflation, anecdote-to-law jumps, totality claims.

Example surface signals:
    "everyone knows", "all experts", "no one disputes", "always",
    "in every case"

----------------------------------------------------------------------
4.7 Tonal Drift
----------------------------------------------------------------------
Detects shifts in register that may indicate structural persuasion.

Markers: neutral-to-charged transitions, analytical-to-emotional shifts.

This is the hardest family to detect deterministically. Initial
implementation may be limited to vocabulary-density comparisons between
text segments (e.g., first half vs second half).

======================================================================
5. DECISION LOGIC
======================================================================

----------------------------------------------------------------------
5.1 Heat Score
----------------------------------------------------------------------

heat_score is the sum of all fired signal weights.

Each detector family contributes independently. A signal fires only
when its pattern threshold is met (threshold details are implementation,
not blueprint).

----------------------------------------------------------------------
5.2 Heat Level
----------------------------------------------------------------------

heat_level is derived from heat_score using categorical thresholds.

    low         Below threshold T1
    moderate    Between T1 and T2
    high        Above T2

T1 and T2 are tuning parameters, not locked by this blueprint.

----------------------------------------------------------------------
5.3 Clean Candidate Rule
----------------------------------------------------------------------

is_clean_candidate is true only when:

    1. heat_level == "low"
    2. No scanner-level contradiction to early termination is present

Scanner-level contradictions include:
    - Any single signal with weight above a high-signal threshold
    - Tonal drift detected (even if aggregate heat is low)
    - detector_count >= contradiction threshold (multiple weak families
      firing together may indicate distributed persuasion)

is_clean_candidate == true does NOT mean the object is clean.
It means L3 found no scanner-level reason to block early termination.

The final clean/escalate decision belongs to L5 and remains provisional
until L4 baseline audit is complete.

======================================================================
6. CONSTRAINTS — WHAT L3 MUST NEVER DO
======================================================================

1. No motive inference.
   L3 detects structural signals. It does not infer why they exist.

2. No propaganda label.
   L3 does not classify objects as propaganda, advocacy, or any
   identity label. It reports heat, not diagnosis.

3. No functional mode guess.
   L3 does not attempt to determine what the object is "really doing."
   That is L6 (functional mode detection).

4. No deep PEG.
   L3 does not compute persuasion-evidence gap. PEG requires claim
   extraction and evidence evaluation, which are L6 operations.
   L3 operates on surface text only.

5. No article-quality verdict.
   L3 does not judge whether the object is good, bad, reliable, or
   misleading. It detects persuasive heat. Period.

6. No AI.
   L3 is fully deterministic. Regex, vocabulary counts, statistical
   measures only. No model calls.

======================================================================
7. WHAT L3 CANNOT KNOW
======================================================================

L3 operates on surface text. It cannot determine:

- Whether persuasive language is appropriate to the mode
  (argument-mode text is expected to persuade; L4 evaluates discipline)

- Whether claims are supported by evidence
  (that requires claim extraction, which is L6)

- Whether the object's presented mode matches its functional mode
  (that requires interpretive analysis, which is L6)

- Whether omissions are significant
  (that requires domain knowledge, which is L6)

- Whether authority citations are real
  (that requires verification, which is outside current scope)

L3 is structurally blind to context. It sees heat. It does not see
whether the heat is justified. That is the job of later layers.

======================================================================
8. INTERACTION WITH LATER LAYERS
======================================================================

----------------------------------------------------------------------
8.1 L5 — EvaluationPlan
----------------------------------------------------------------------

PersuasionResult feeds directly into EvaluationPlan construction.

L5 uses:
    heat_level      → escalation_level determination
    is_clean_candidate → stop_early_allowed determination
    signals         → allowed_deep_modules selection
    detector_count  → distributed persuasion assessment

----------------------------------------------------------------------
8.2 Clean Finding Path (L8)
----------------------------------------------------------------------

When is_clean_candidate is true AND L5 confirms stop_early_allowed:

    L4 baseline audit runs (cheap, deterministic)
    If L4 passes → clean finding report (L8)
    No AI layers activated

----------------------------------------------------------------------
8.3 Escalation Path
----------------------------------------------------------------------

When heat_level is moderate or high:

    L5 constructs EvaluationPlan with escalation
    L5 authorizes specific deep modules based on which
        detector families fired
    Router (L5) activates only authorized modules

L5 authorizes only the deep modules relevant to the fired detector
families and concern profile.

Selective escalation. Not monolithic.

----------------------------------------------------------------------
8.4 Mode-Aware Weighting (optional, not required for Stage 2)
----------------------------------------------------------------------

When mode_result is available, L3 may adjust signal weights based on
presented mode. For example:

    argument mode → directional_persuasion weight reduced
                    (expected in argument discourse)
    witness mode  → directional_persuasion weight increased
                    (unexpected in witness discourse)

This is a refinement, not a requirement. Stage 2 implementation may
use uniform weights and defer mode-aware weighting to a later stage.

======================================================================
9. STAGE 2 BUILD SCOPE
======================================================================

Stage 2 builds L3 as a standalone module.

Will build:
    engine/analysis/persuasion_screen.py
    tests/test_persuasion_screen.py

Will not build:
    L5 integration (Stage 3)
    Mode-aware weighting (deferred)
    Tonal drift detection (may be stub or deferred)
    Threshold tuning (provisional values only)

Stage 2 output must be testable in isolation.
Stage 2 must not import from or depend on pipeline.py.
Stage 2 must not modify any existing files.

======================================================================
END OF STAGE 2 LOGIC BLUEPRINT
======================================================================
