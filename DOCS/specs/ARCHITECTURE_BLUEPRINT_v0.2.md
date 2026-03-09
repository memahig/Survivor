BIASLENS / SURVIVOR — ARCHITECTURE BLUEPRINT
VERSION: 0.2
STATUS: PRE-BUILD LOCK
DATE: 2026-03-08

======================================================================
ARCHITECTURAL CLARIFICATION: EVALUATION ENGINE
======================================================================

The architecture described in this blueprint refers specifically to the
BiasLens **Epistemic Evaluation Engine**, which evaluates individual
information objects.

This subsystem performs structured epistemic analysis of an object and
determines how much reliable information can be recovered from it.

Other BiasLens components (such as corpus analysis, narrative propagation
analysis, and accountability artifact generation) operate above this layer.

The Evaluation Engine therefore functions as an **epistemic triage system**
for individual objects, determining whether deeper analysis is required.

======================================================================
1. PURPOSE
======================================================================

This document defines the stable architecture of the BiasLens / Survivor
evaluation system prior to implementation.

The purpose of this blueprint is to lock:

* System structure
* Layer responsibilities
* Evaluation flow
* Escalation logic
* Data movement
* AI usage boundaries
* Doctrine invariants

Detector details, thresholds, scoring weights, and prompts remain flexible
and intentionally unlocked.

BiasLens is designed as an **epistemic triage engine**, not a monolithic
AI analyzer.

Core design principle:

    Mode first.
    Minimum necessary evaluation first.
    Escalate only when concern signals justify deeper analysis.
    Offload as much work from AI as possible without compromising accuracy.

======================================================================
2. DOCTRINAL FOUNDATIONS (LOCKED)
======================================================================

2.1 Core Mission
BiasLens evaluates information objects and determines how much epistemically
reliable information can be recovered from them.

The system does not attempt to determine absolute truth.

Instead, it evaluates:

* the evidentiary support behind claims
* the persuasive structure of the object
* the epistemic duties appropriate to the object's discourse mode
* the degree to which persuasion exceeds evidence

2.2 Primary Question

    "Is the reader being shown, or being moved?"

2.3 PEG Principle
Persuasion-Evidence Gap (PEG) is a warning signal, not a verdict.

PEG indicates persuasive architecture may exceed evidentiary support.

2.4 Mode Before Analysis
Every object must be classified by epistemic mode before deeper analysis.

2.5 Mode-Specific Duty
Each object is evaluated against the obligations of its mode, not against
a universal "perfect article."

2.6 Universal Persuasion Screen
Every object is screened for persuasive activity.

Not every object receives full persuasion analysis.

2.7 Accuracy-Preserving AI Minimization
Deterministic and rule-based analysis is preferred where accuracy allows.

AI inference is used only where interpretation is required.

2.8 Escalate Rather Than Overclaim
If deterministic methods cannot produce reliable results, the system escalates.

2.9 No Intent Attribution
The system may describe structure and reader effect.
It must not infer author intent.

2.10 Self-Application
BiasLens outputs remain analyzable by the same framework.

======================================================================
3. TOP-LEVEL SYSTEM SHAPE
======================================================================

BiasLens operates as a layered epistemic triage engine.

    L0  Structural ingest
    L1  Object normalization
    L2  Presented mode classification
    L3  Universal persuasion screen
    L4  Mode-specific baseline audit
    L5A Escalation policy
    L5B Evaluation router
    L6  Single-model interpretive evaluation
    L7  Multi-model arbitration (Survivor)
    L8  Synthesis / report composition
    L9  Cross-article / corpus comparison (BiasLens+)

Most objects terminate early.

Deep AI layers run only when necessary.

======================================================================
4. CORE DATAFLOW
======================================================================

Canonical flow:

    raw object
      ->
    structural ingest
      ->
    normalized object
      ->
    presented mode classification
      ->
    persuasion screen
      ->
    mode-specific baseline audit
      ->
    escalation decision
      ->
    if escalation = none
        clean finding / limited report
    elif escalation = reviewer
        single-model interpretive evaluation
    elif escalation = full
        Survivor arbitration
      ->
    synthesis
      ->
    optional corpus comparison

Escalation is a **branching decision**, not merely annotation.

======================================================================
5. EPISTEMIC MODE FRAMEWORK
======================================================================

Core modes:

    witness
    proof
    rule
    explanation
    argument
    experience
    record
    voice
    formal
    uncertain (fail-closed)

Formal submodes:

    logic
    mathematics

Mode definitions:

witness
    Attribution-bound reporting of observed events or statements.

proof
    Evidence-bound empirical claims.

rule
    Procedure-bound application of law or policy.

explanation
    Causal interpretation of events.

argument
    Advocacy-driven persuasion toward a thesis.

experience
    Narrative testimony from lived perspective.

record
    Reference or catalog-style information storage.

voice
    Institutional communication from organizations or power centers.

formal
    Deductive reasoning using definitions, axioms, or prior results.

uncertain
    Fail-closed classification state.

======================================================================
6. PRESENTED MODE VS FUNCTIONAL MODE
======================================================================

presented_mode
    Determined early using deterministic signals.

functional_mode
    Determined later via interpretive analysis.

Mode camouflage occurs when:

    presented_mode != functional_mode

Example:

    presented explanation -> functional argument

The mismatch itself is a finding.

======================================================================
6A. ARTICLE MODE VS CLAIM STRUCTURE
======================================================================

BiasLens distinguishes between:

Article Mode
    The discourse form the object appears to be operating within
    (witness, proof, explanation, argument, etc.).

Claim Structure
    The individual claims contained within the object.

Functional Mode
    The structural role the object ultimately performs after evaluation.

An object may present itself as one discourse type but function as another.
This gap is known as **mode camouflage**.

Example:

    presented_mode: explanation
    functional_mode: argument

======================================================================
7. ARTICLE STRUCTURE RULE
======================================================================

BiasLens does not assume a fixed number of article layers.

Articles are represented as **slot-aware structural graphs**.

Possible slots include:

    title
    subtitle / dek
    lead
    section headers
    body
    captions
    pull quotes
    quote blocks
    sidebars
    metadata fields

The architecture requires **preservation of structure**, not a fixed slot count.

This supports:

* headline-body concordance
* presentation integrity analysis
* quote localization
* constraint-drop detection
* corpus comparison

======================================================================
8. LAYER RESPONSIBILITIES
======================================================================

L0 — Structural Ingest
Convert raw object into slot-aware structure.

Must preserve presentation hierarchy.

L1 — Normalization
Clean text and metadata.

No interpretation allowed.

L2 — Presented Mode Classification
Determine surface discourse type.

Cheap deterministic signals only.

L3 — Universal Persuasion Screen
Cheap persuasion "heat" detection.

Detect:

* certainty escalation
* moral loading
* existential framing
* authority substitution
* directional persuasion
* universalization
* tonal drift
* constraint drop

Low heat does NOT clear the object.
It only indicates no strong linguistic signal.

L4 — Mode-Specific Baseline Audit
Check duties appropriate to the mode.

Examples:

Witness
    attribution discipline
    causal restraint
    source asymmetry

Proof
    data-to-claim proportionality

Explanation
    causal integrity

Argument
    structural persuasion discipline

Formal
    deductive validity

Subroutine inventories remain flexible.

======================================================================
9. ESCALATION ARCHITECTURE
======================================================================

L5A — Escalation Policy

Determines escalation level:

    none
    reviewer
    full

Inputs:

* mode confidence
* persuasion heat
* baseline audit results
* structural anomalies

Rule:

    uncertain mode -> reviewer minimum

L5B — Evaluation Router

Activates deeper modules based on escalation decision.

Escalation is **selective**, not monolithic.

Example:

A witness article with source asymmetry may escalate to attribution
analysis without triggering full PEG analysis.

======================================================================
10. AI INTERPRETATION
======================================================================

L6 — Single-Model Interpretive Evaluation

Used when deterministic layers are insufficient.

Tasks include:

* functional mode detection
* argument reconstruction
* omission significance
* causal integrity analysis
* camouflage detection

Outputs structured JSON.

======================================================================
11. MULTI-MODEL ARBITRATION
======================================================================

L7 — Survivor Arbitration

Used only when:

* persuasion heat is high
* structural concerns are severe
* reviewers disagree
* mode camouflage is suspected

Survivor compares outputs from multiple models and produces reconciled
structured findings.

======================================================================
12. SYNTHESIS
======================================================================

L8 — Report Composition

Possible outputs:

* clean finding report
* limited baseline report
* blunt summary
* reader in-depth
* scholar in-depth
* technical debug report

======================================================================
13. CLEAN FINDING RULE
======================================================================

A clean finding is a valid affirmative output.

Conditions:

    mode confidence sufficient
    persuasion heat low
    baseline duties satisfied
    no structural anomalies detected

Output example:

    escalation_level: none
    finding: clean
    summary:
        "This object meets its epistemic obligations for
         [mode]-mode discourse."

Renderer must support clean findings.

======================================================================
14. COMPUTE OPTIMIZATION RULES
======================================================================

1. No AI before deterministic layers.
2. Clean low-concern cases terminate early.
3. Escalation runs only required modules.
4. Every expensive module requires a trigger.
5. Accuracy overrides cheapness.

======================================================================
15. EXISTING MODULE MIGRATION
======================================================================

Existing deep-analysis modules are assumed to belong to L6 unless they
can be safely migrated into L4 baseline audits.

Baseline audits should remain lightweight.

======================================================================
16. UNCERTAINTY HANDLING
======================================================================

The system must explicitly represent uncertainty states:

    uncertain mode
    insufficient evidence
    ambiguous structure
    unresolved reviewer disagreement

Unknown is a valid output.

======================================================================
17. BUILD SEQUENCE
======================================================================

Stage 1
Mode spine

Stage 2
Universal persuasion screen

Stage 3
Escalation router

Stage 4
Mode-specific baseline audits

Stage 5
Single-model interpretation

Stage 6
Survivor arbitration

Stage 7
Report refinement

Stage 8
Corpus-level BiasLens+

======================================================================
18. CORE ARCHITECTURAL SUMMARY
======================================================================

BiasLens operates as an epistemic triage system.

The system first determines the discourse mode of the object,
then evaluates the object against the obligations of that mode.

Every object receives a persuasion screen.

Only objects showing epistemic risk escalate into deeper analysis.

This architecture ensures:

* compute efficiency
* doctrinal discipline
* low false positives
* extensibility
* interpretability

END OF BLUEPRINT
