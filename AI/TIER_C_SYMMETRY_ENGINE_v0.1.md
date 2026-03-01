# FILE: AI/TIER_C_SYMMETRY_ENGINE_v0.1.md
# PROJECT: Survivor
# LAYER: Architecture (Governing Spec — Tier C)
# STATUS: LOCKED
# VERSION: 0.1
# AUTHORITY: Michael (Final Arbiter)
# DEPENDS_ON:
#   - Tier A Structural Validation
#   - Structured Inference Packets
#   - Deterministic Swap Transform
# SUPERSEDES: None
# SUPERSEDED_BY: (future versions only via explicit version bump)
# IMPLEMENTATION_TARGETS:
#   - engine/core/pipeline.py
#   - engine/arena/judge.py
#   - engine/eo/symmetry.py (new module)
#
# PRINCIPLE:
# Symmetry is a calibrated, field-scoped invariance test.
# It operates only on structured packets.
# It never uses natural-language prompting.
# It never silently alters adjudication weights.
# It quarantines only contaminated fields.

SPEC: SYMMETRY ENGINE — CALIBRATED SCOPED QUARANTINE (v0.1)
STATUS: LOCKED
OWNER: Michael (final arbiter)
SCOPE: Survivor adjudication Tier C (Symmetry) operating ONLY on structured packets
NOTE: No natural-language swap prompting is permitted. Swap is deterministic code.

------------------------------------------------------------
1) PURPOSE
------------------------------------------------------------
Detect identity-dependent reasoning by comparing:
- Packet P (original)
- Packet P' (identity/role swapped via deterministic transform)

If symmetry divergence is large enough to exceed calibrated thresholds,
quarantine only the contaminated fields (set to UNKNOWN), preserving clean fields.

This is an epistemic hygiene mechanism:
- Preserve maximum reliable information
- Quarantine identity-sensitive inferences
- Never "repair" or rewrite outputs

------------------------------------------------------------
2) NON-NEGOTIABLE CONSTRAINTS
------------------------------------------------------------
(A) POST-EXTRACTION ONLY:
    Symmetry testing operates only on structured packets.
    No LLM is asked to "imagine" swaps or hypotheticals.

(B) DETERMINISTIC TRANSFORM:
    The swap is performed by code:
      actor_A ↔ actor_B
      role_A  ↔ role_B
    No other fields are modified by the swap transform.

(C) UNKNOWN-FIRST:
    If required swap fields are missing or undefined, Tier C returns:
      symmetry_status = UNKNOWN
    and performs no quarantine.

(D) SOFT FLAG IS AUDIT-ONLY (NON-LOAD-BEARING):
    soft_symmetry_flag has ZERO mechanical effect on:
      - weights
      - consensus
      - verdicts
      - adjudication ordering
    It is logging/annotation only.
    Any downstream use that changes outcomes is prohibited.

------------------------------------------------------------
3) INPUTS
------------------------------------------------------------
Input packets must be structured and schema-validated (Tier A) before Tier C runs.

Required fields for Tier C:
- actor_A, actor_B, role_A, role_B  (for deterministic swap)
- symmetry_fields: fixed list of fields evaluated for symmetry
- each field value must be categorical or ordinal with enumerated vocabulary

No prose fields are used in Tier C.

------------------------------------------------------------
4) SYMMETRY FIELDS (v0.1 BASE SET)
------------------------------------------------------------
Symmetry is computed over the following fields unless overridden by config:

CATEGORICAL:
- classification_bucket          (e.g., reporting/analysis/advocacy/propaganda_patterned_advocacy/satire_like/unknown)
- intent_level                   (none/negligence/reckless/intentional/unknown)
- requires_corrob                (true/false)
- omission_load_bearing          (true/false)

ORDINAL:
- severity_tier                  (low/moderate/high/critical/unknown)
- confidence_band                (low/medium/high/unknown)

Atomicity rule:
- Each listed field is treated as an atomic unit for symmetry.
- If a "compound" label exists in future, it must be decomposed before Tier C.

------------------------------------------------------------
5) DISTANCE FUNCTION (FIELD-LEVEL)
------------------------------------------------------------
For each symmetry field f, compute d_f in [0,1]:

Binary/Categorical fields:
- d_f = 0 if value(P,f) == value(P',f)
- d_f = 1 otherwise
- if either value is UNKNOWN → d_f is marked "indeterminate" (see Section 7)

Ordinal fields (severity_tier, confidence_band):
- map each enum to an index (monotone)
- if either value is UNKNOWN → "indeterminate"
- else:
    d_f = abs(idx(P,f) - idx(P',f)) / (max_idx - min_idx)

------------------------------------------------------------
6) AGGREGATE DELTA (Δ)
------------------------------------------------------------
Compute aggregate symmetry delta Δ in [0,1]:

Δ = Σ (w_f * d_f) over all determinate fields

Where:
- weights w_f are config-driven
- weights sum to 1 over the included determinate fields
- if no determinate fields exist → symmetry_status = UNKNOWN

Default (v0.1) weights (example; may be calibrated):
- classification_bucket: 0.25
- intent_level:          0.25
- severity_tier:         0.20
- requires_corrob:       0.10
- omission_load_bearing: 0.10
- confidence_band:       0.10

------------------------------------------------------------
7) UNKNOWN HANDLING (FIELD-LEVEL)
------------------------------------------------------------
If a field is UNKNOWN in either packet:
- It does NOT contribute to Δ (indeterminate)
- It is NOT quarantined by Tier C (it is already UNKNOWN)
- It is recorded in symmetry_quarantine.notes as "indeterminate_field"

This prevents "quarantining" based on missing data.

------------------------------------------------------------
8) CALIBRATED THRESHOLDS (ε and τ)
------------------------------------------------------------
Two config-driven thresholds:

- ε (epsilon): noise floor (expected jitter tolerance)
- τ (tau): contamination threshold (identity-sensitive divergence)

Config location (normative): symmetry_settings.epsilon, symmetry_settings.tau
Weights: symmetry_settings.weights
Fields: symmetry_settings.symmetry_fields
(Implementations must not infer alternate config paths.)

Policy uses three zones:

Zone 1: Δ ≤ ε
- symmetry_status = PASS
- no quarantine
- no flags

Zone 2: ε < Δ < τ
- symmetry_status = SOFT_FLAG
- emit soft_symmetry_flag = true
- NO quarantine
- IMPORTANT: soft_symmetry_flag is audit-only, non-load-bearing (Section 2D)

Zone 3: Δ ≥ τ
- symmetry_status = QUARANTINE
- quarantine only contributing fields (see Section 9)

Calibration note:
- ε and τ are treated as instrument calibration parameters.
- Defaults may be conservative; real-world calibration is expected.

------------------------------------------------------------
9) QUARANTINE RULE (SCOPED)
------------------------------------------------------------
When Δ ≥ τ:

Quarantine set Q consists of fields that materially contributed:
- include any field f with d_f > 0 (and determinate)
- Fields with d_f == 0 are NEVER quarantined.
- Indeterminate fields (UNKNOWN in either packet) are NEVER quarantined by Tier C.
- set packet field f = UNKNOWN for downstream adjudication
- preserve all non-quarantined fields unchanged

This is surgical quarantine:
- no model removal
- no whole-output unknown unless all fields are quarantined/unknown
- no rewriting or "repairing" values

------------------------------------------------------------
10) OUTPUT ARTIFACT (Tier C Block)
------------------------------------------------------------
Tier C emits a symmetry block:

{
  "symmetry_status": "UNKNOWN|PASS|SOFT_FLAG|QUARANTINE",
  "delta": Δ (if determinate else null),
  "epsilon": ε,
  "tau": τ,
  "soft_symmetry_flag": true|false,
  "quarantine_fields": [ ... ]          (only when QUARANTINE)
  "field_deltas": { f: d_f or null },   (null for indeterminate)
  "notes": [ ... ]                      (indeterminate fields, missing swap keys, etc.)
}

In QUARANTINE, the engine MUST also emit a "receipt":
- field name
- observed d_f
- reason: identity_swap_divergence
- (optional) pointer to which upstream packet produced the field

------------------------------------------------------------
11) ADJUDICATION INTERACTION (STRICT)
------------------------------------------------------------
- Tier C runs AFTER Tier A validation.
- Tier B consensus operates ONLY on post-quarantine packets.
- soft_symmetry_flag has ZERO effect on Tier B weights or verdict.
- Quarantined fields (UNKNOWN) are treated as missing; Tier B cannot infer them.

------------------------------------------------------------
12) PROHIBITIONS
------------------------------------------------------------
- No prompt-based swap tests.
- No prose-based similarity checks.
- No "penalty curves" hidden behind soft flags.
- No use of soft_symmetry_flag to influence any adjudication outcome.
- No silent upgrades of field set, weights, ε, τ without explicit version bump.

END SPEC
