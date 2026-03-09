# BIASLENS / SURVIVOR — SESSION STATE
DATE: 2026-03-08
STATUS: DRIFT AUDIT COMPLETE / EPISTEMIC MODE BUILD PHASE NEXT

---

## Session Summary (2026-03-08, continued)

### Drift Audit — Reviewer Prompt Governance

Claude (Code Author) accepted the role of **guardian of drift** — responsible for
ensuring evaluating AIs receive doctrine-aligned instructions and that the codebase
does not silently diverge from the constitutional layer.

**Audit scope**: Mapped all reviewer prompts (`survivor_boot.txt` v2.4, phase-specific
prompts in adapter files, `builder.py`, `gsae_extraction.txt`) against the full
governance stack (Manifesto, PEG Doctrine v1.1, Canonical Spec v1.2, BiasLens
Doctrine v1.0, Foundational Principle).

### Drift Findings (6 identified)

#### 1. Propaganda-Centric Framing (HIGH priority)
The boot defines a "Propaganda Threshold" (≥3 structural markers). This frames
evaluation around detecting propaganda. Contradicts Mike's locked principle:
"BiasLens is NOT a propaganda detector. It is an epistemic instrument."

**Impact**: Evaluating AIs are primed to look for problems, not to perform
balanced epistemic assessment. The instrument cannot currently affirm.

#### 2. No Epistemic Mode Awareness (HIGH priority)
The 8 modes (Witness, Proof, Rule, Explanation, Argument, Experience, Record, Voice)
do not exist in the boot. Breaking news judged by same standards as op-ed.
This is the exact false-positive source the doctrine was designed to fix.

#### 3. No "Clean Finding" Concept (HIGH priority)
Boot is entirely deficit-focused. No instruction that "this article meets its
epistemic obligations" is a valid, valuable output. The instrument can only warn.

#### 4. No PEG Scope Gating (MEDIUM priority)
Reviewers don't know PEG should run at different intensities per mode.
Full PEG on breaking news (Witness mode) violates doctrine.

#### 5. No Mode Camouflage Detection (MEDIUM priority)
Reviewers not asked to distinguish presented mode from functional mode.
Advocacy disguised as explanation passes without flag.

#### 6. Missing Mission Statement (LOW priority — but foundational)
Boot says "Constitutional Structural Epistemic Audit" but never states the actual
mission: reveal what information can be structurally gleaned from any object.

### Recommended Fix: Doctrine Preamble
Highest-leverage single change: insert a 15-25 line doctrine preamble at the top
of `survivor_boot.txt` giving every evaluating AI the essential epistemic framing
before operational instructions. Does not require pipeline code changes.

---

## Previous Session Breakthroughs (carried forward)

### PEG Clarified
    Persuasion Strength - Evidence Strength = Epistemic Risk
PEG is a warning signal, not a verdict. BiasLens evaluates whether argument
structure is doing work the evidence has not earned.

### Epistemic Mode Framework (8 modes)
1. Witness (Attribution-bound)
2. Proof (Evidence-bound)
3. Rule (Procedure-bound)
4. Explanation (Explanation-bound)
5. Argument (Advocacy-bound)
6. Experience (Narrative-bound)
7. Record (Reference-bound)
8. Voice (Institutional-bound)

### PEG Scope Rules
- **Full PEG**: Argument, Explanation, Voice
- **Standard PEG**: Proof
- **Limited PEG**: Witness, Rule, Record
- **Minimal PEG**: Experience

### Mode Camouflage Detection
    presented_mode: Explanation
    functional_mode: Argument
    mode_mismatch: TRUE -> reader warning

### Self-Application Clause
BiasLens itself is analyzable by BiasLens. No immunity for any institution,
ideology, or BiasLens itself.

---

## Foundational Principle (Mike, 2026-03-08)

BiasLens is NOT a propaganda detector. It is an epistemic instrument.

Propaganda was the stress test — the hardest case where LLMs, institutions, and
social pressure all conspire to soften findings. That's why development started
there. But it is not the mission.

The mission: **reveal what information can be structurally gleaned from any object,
and eventually where that object sits in the real world.**

BiasLens must be equally capable of saying:
- "This news report is doing exactly what news should do"
- "This research paper's conclusions match its data"
- "This op-ed is transparent advocacy with fair engagement"
- "This institutional statement presents interest as fact"

A clean finding ("this object meets its epistemic obligations") is as valuable
as a warning. All eight modes matter equally.

---

## Title-Body Structural Separation (2026-03-08)

**Identified regression**: evidence bank flattens title and body into one
undifferentiated line sequence. Title repeated in lead creates duplicate EID crash.

**Mike's insight**: title is a separate epistemic object. Title-body concordance
is itself evidence — enables clickbait detection, headline escalation, constraint-
dropping, underselling (neutral headline on propaganda body).

**Correct fix** (trilateral consensus): slot-aware evidence records with
structural position metadata (title, subtitle, lead, body, caption, quote block).
Duplicate quote check applies within slots, not across them. NOT simple dedup.

**Pipeline-killing bug**: `duplicate quote at 'E2'` — awaiting proper slot-aware
fix. No quick patch applied per Mike's direction ("build it right").

**Locked principle**: "The title is not just another quote. It is a presentation-
layer object that must remain structurally distinct from the body so BiasLens can
evaluate concordance, escalation, and presentation integrity."

---

## Session Fixes Applied (2026-03-08)

1. Claude reviewer retry/backoff + temperature=0.0 (adapter-level, loud debt note)
2. Layer 8 normalizer: object_discipline_check repair
3. Anthropic API key replaced (old key had billing mismatch)
4. Validator off-ramp fix (from previous session, confirmed working)

---

## Current System State

Working:
- Survivor multi-reviewer arbitration (3 real reviewers + mocks)
- Evidence-indexed analysis pipeline (two-pass Phase 1 + Phase 2)
- Blunt Report output (3-tab Streamlit UI)
- Structural persuasion detection (9 analysis modules)
- PEG v1.1 (locked, wired)
- BiasLens corpus exporter (in-memory zip download)
- Validator off-ramp alignment
- GSAE Tier-C symmetry engine
- Layer 7 EID sanitization + Layer 8 object_discipline_check repair

Not yet implemented:
1. Epistemic mode classifier
2. Mode-specific evaluation logic
3. Mode camouflage detector
4. PEG scope gating
5. Argument structure reconstructor
6. Report composer / synthesis layer
7. Omission repair module
8. Self-analysis capability
9. Doctrine preamble for reviewer boot prompt
10. Slot-aware evidence bank (title/body structural separation)
11. Shared transport/retry abstraction (provider parity)

Test suite: 686 passing.
Pipeline blocked by: duplicate quote crash (awaiting slot-aware evidence bank).

---

## NEXT SESSION: Build Plan — Epistemic Mode Classifier

### Overview
The mode classifier is the **first gate** in the doctrine pipeline. It determines
what kind of discourse the article represents BEFORE any evaluation occurs.
Without it, every article is judged by the same standards — the root cause of
false positives on news and false negatives on camouflaged advocacy.

### Architecture Decision Required (Trilateral)

**Option A: Rule-based classifier (deterministic)**
- Pattern matching on structural signals (attribution density, evidence density,
  imperative language, institutional markers, narrative markers)
- Pro: deterministic, testable, no LLM dependency
- Con: brittle on edge cases, can't detect camouflage without deeper reading

**Option B: Reviewer consensus (LLM-assisted)**
- Each reviewer independently classifies the mode as part of Phase 1
- Adjudicate across reviewers like any other claim
- Pro: leverages LLM reading comprehension, catches camouflage
- Con: adds LLM dependency to a gate that controls LLM evaluation scope

**Option C: Hybrid (recommended by Claude)**
- Rule-based first pass produces a candidate mode with confidence
- If confidence is high → use it (deterministic path, no LLM cost)
- If confidence is low or mode signals conflict → flag for reviewer classification
- Reviewer classification in Phase 1 can confirm or override
- Camouflage detection: compare rule-based (presented) vs reviewer (functional)
- Pro: deterministic where possible, LLM-assisted where needed, natural
  camouflage detection from the gap between the two
- Con: more complex implementation

### Implementation Plan (assuming Option C approved)

#### Step 1: Doctrine Preamble for Boot Prompt
- Insert epistemic mode awareness into `survivor_boot.txt`
- Reviewers learn the 8 modes and their obligations
- Reviewers instructed to classify mode as part of Phase 1 output
- **No pipeline code changes required** — prompt-only change
- This is the single highest-leverage change for drift prevention

#### Step 2: Mode Classifier Module (`engine/analysis/mode_classifier.py`)
- Pure function: `classify_mode(normalized_text, config) -> ModeResult`
- Input: normalized article text
- Output:
  ```
  {
    "presented_mode": str,        # one of 8 modes
    "confidence": float,          # 0.0-1.0
    "signals": [...],             # structural signals that drove classification
    "requires_reviewer_confirm": bool  # True if confidence < threshold
  }
  ```
- Structural signals to detect:
  - Attribution density (Witness: high attribution, low assertion)
  - Evidence citation density (Proof: high citation, formal structure)
  - Procedural/regulatory language (Rule)
  - Balanced explanation markers (Explanation: multiple perspectives presented)
  - Advocacy markers (Argument: directional language, call to action)
  - First-person narrative (Experience)
  - Reference/catalog structure (Record)
  - Institutional voice markers (Voice: "we", organizational framing)
- No external dependencies. Deterministic. Fail-closed to "uncertain".

#### Step 3: Phase 1 Prompt Update
- Add `epistemic_mode` to Phase 1a triage output schema:
  ```
  "epistemic_mode": {
    "presented_mode": str,
    "functional_mode": str,
    "mode_confidence": "low" | "medium" | "high",
    "mode_mismatch": bool,
    "mismatch_explanation": str | null
  }
  ```
- Reviewers independently assess both presented and functional mode
- This is where camouflage detection naturally emerges

#### Step 4: Mode Adjudication
- After Phase 1, adjudicate mode across reviewers
- If rule-based and reviewer consensus agree → high confidence
- If they disagree → mode_mismatch flag, lower confidence
- Output feeds into PEG scope gating

#### Step 5: PEG Scope Gating
- Wire mode classification into PEG evaluation
- Full/Standard/Limited/Minimal PEG based on adjudicated mode
- Modify `substrate_enricher.py` to pass mode to PEG module
- PEG module already exists — this adds a gate, not new logic

#### Step 6: Normalizer Layer for Mode (Drift Firewall)
- Add Layer 9 to `normalize_reviewer_pack()` in validators.py
- Normalize mode strings (e.g., "news" → "witness", "opinion" → "argument")
- Clamp to authorized enum values
- Unknown → "uncertain"

### Dependencies
- Step 1 (preamble) has zero code dependencies — can ship immediately
- Steps 2-3 can develop in parallel
- Step 4 requires both 2 and 3
- Step 5 requires 4
- Step 6 should ship with Step 3

### Parallel Track: Slot-Aware Evidence Bank (Pipeline Unblock)
Still needed to unblock the pipeline (duplicate quote crash).
Can develop independently of mode classifier.
See Title-Body Structural Separation section above.

**ChatGPT's recommended first action**: Design the slot-aware Evidence Bank
JSON schema before writing code. This anchors the entire Phase 2 build.

Proposed schema (needs trilateral approval):
```json
{
  "eid": "E1",
  "quote": "verbatim text",
  "locator": {
    "char_start": int,
    "char_end": int
  },
  "source_id": "A-<hash>",
  "locations": [
    {"slot": "title", "index": 0},
    {"slot": "body", "index": 0}
  ]
}
```
Rules:
- Identical text across slots shares ONE eid
- `locations` array records all structural positions
- Evidence counted once for PEG (not per-location)
- Slot metadata preserved for presentation analysis
- Duplicate quote check applies WITHIN slots, not across

Required ingest changes:
- `ingest.py` → extract title (field exists, never populated)
- `normalize.py` → aware of title vs body
- `pipeline.py` → pass title to evidence bank
- `evidence_bank.py` → slot-aware chunker
- `validators.py` → allow multi-slot evidence

### Coordinator's Phase 2 Module Map (ChatGPT, 2026-03-08)

Unified with Claude's 6-step plan:

| # | Module | Purpose | Depends On |
|---|--------|---------|------------|
| 1 | Structural Ingest | Extract title, separate body, assign slots | — |
| 2 | Slot-Aware Evidence Bank | Multi-location evidence records | Module 1 |
| 3 | Doctrine Preamble | Align reviewer prompts with mission | — |
| 4 | Epistemic Mode Classifier (EMS) | Identify presented_mode from structure | — |
| 5 | Functional Mode Detector | Identify functional_mode from reviewer analysis | Modules 3, 4 |
| 6 | Headline-Body Concordance | Clickbait, escalation, constraint-dropping | Modules 1, 2 |
| 7 | PEG Scope Gating | Full/Standard/Limited/Minimal per mode | Module 5 |
| 8 | Pass B Evaluator | Best-explanation synthesis from all signals | All above |

**Critical path**: Modules 1-2 unblock the pipeline. Module 3 can ship in parallel.
Module 4 can develop in parallel. Modules 5-8 require earlier modules.

### BiasLens vs BiasLens+ Boundary (ChatGPT, 2026-03-08)

**BiasLens** (current scope):
- Single-article structural analysis
- Detects: propaganda-patterned structures, PEG, framing control, omission patterns
- Language: "propaganda-patterned properties"

**BiasLens+** (future scope):
- Multi-article / narrative-level evidence
- May escalate classification when cross-article patterns exist
- Language: "appears to be propaganda"

This boundary is doctrinal, not yet implemented.

---

## Canonical Test Case
Halevi article ("This Dangerous Jewish Moment") successfully triggered
propaganda-patterned advocacy signals through deterministic structural analysis.
Confirms system can overcome LLM bias toward soft labeling.

---

## BiasLens Doctrine v1.0
Project location: `DOCS/doctrine/biaslens_doctrine_v1.md`

Key sections:
1. Core Principle — epistemic safety, not fact-checking
2. PEG — persuasion-evidence gap as core diagnostic
3. Self-Application Clause
4. Epistemic Mode Classification (8 modes)
5. Epistemic Duty Matrix (per-mode obligations)
6. Mode Camouflage Detection
7. PEG Scope Rules
8. Reader Warning System
9. Foundational Rules (7 non-negotiable)
10. Doctrine Statement
