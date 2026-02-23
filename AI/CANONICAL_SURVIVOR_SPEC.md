# BiasLensSurvivor — Canonical Control Specification v1.2
Status: LOCKED
Audience: AI Agents
Purpose: Machine-readable invariants and execution constraints

============================================================
[ID:SURVIVOR-IDENTITY-001]
SYSTEM IDENTITY
============================================================

BiasLensSurvivor is a multi-model epistemic constraint engine.

It evaluates:
- structural integrity
- evidentiary tethering
- proportionality
- responsiveness
- cross-model stability

It does NOT:
- certify truth
- infer intent
- assign ideological direction
- issue binding verdicts

All outputs are provisional.

============================================================
[ID:SURVIVOR-INVARIANT-UNCERTAINTY-001]
UNCERTAINTY FIRST
============================================================

System must support:
- unknown
- insufficient_evidence
- contested

Absence must be declared explicitly.

Fail if silent.

============================================================
[ID:SURVIVOR-INVARIANT-NO-INTENT-002]
NO INTENT INFERENCE
============================================================

Omission = absence_of_expected_context

Never:
- motive attribution
- wrongdoing inference

============================================================
[ID:SURVIVOR-INVARIANT-EVIDENCE-003]
EVIDENCE-INDEXED FINDINGS ONLY
============================================================

No finding without:
- internal evidence IDs
OR
- explicit unknown state

============================================================
[ID:SURVIVOR-INVARIANT-DOCUMENT-AUTHORITY-004]
DOCUMENT AUTHORITY GATE
============================================================

If claim_type == document_content:
  require:
    primary_source_quote
    citation_locator

If missing → FAIL RUN

Primary text supersedes interpretive summaries.

============================================================
[ID:SURVIVOR-INVARIANT-AUTHORITY-SCOPE-005]
AUTHORITY IS DOMAIN-SCOPED
============================================================

Authority = procedural stability.

No source is infallible.
Tiering increases evidentiary weight, not certainty.

============================================================
[ID:SURVIVOR-CLAIM-TYPES-006]
CLAIM TYPE ENUMERATION
============================================================

document_content
historical_claim
scientific_claim
legal_claim
causal_claim
statistical_claim
normative_claim
interpretive_claim

Document authority applies ONLY to document_content.

============================================================
[ID:SURVIVOR-ARCHITECTURE-007]
FIVE-LAYER EXECUTION MODEL
============================================================

Layer 1 → Independent Structural Reconstruction
Layer 2 → Structured Cross-Review
Layer 3 → Weighted Epistemic Convergence
Layer 4 → Counterfactual Reversal Stress Test
Layer 5 → Stability-Adjudicated Output

============================================================
[ID:SURVIVOR-DETERMINISTIC-EVASION-008]
EVASION COEFFICIENT (DETERMINISTIC)
============================================================

evasion_coefficient =
  question_specificity_score - answer_responsiveness_score

Models supply inputs.
System computes final value.

============================================================
[ID:SURVIVOR-CONVERGENCE-LIMIT-009]
CONVERGENCE LIMITATION
============================================================

Cross-model agreement is:
  necessary but not sufficient.

System must:
  detect structural redundancy
  flag monoculture risk

============================================================
[ID:SURVIVOR-EXTERNAL-VERIFICATION-010]
EXTERNAL VERIFICATION STATUS
============================================================

Architecturally committed.
NOT implemented in v1.2.
Scheduled for v1.3 subsystem.

When implemented:
  - evidence-indexed statuses only
  - no true/false outputs
  - explicit uncertainty required

============================================================
[ID:SURVIVOR-REPORT-FOOTER-011]
REPORT FOOTER REQUIREMENT
============================================================

Every report must include:

"This analysis evaluates epistemic structure and evidence recoverability.
No source is treated as infallible. Findings are provisional and subject to revision."