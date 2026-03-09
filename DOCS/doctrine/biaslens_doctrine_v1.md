# BiasLens Doctrine v1.0
### The Constitutional Layer

---

## 1. Core Principle

BiasLens is an epistemic safety system.

It does not fact-check. It does not determine truth. It does not accuse authors of intent.

BiasLens identifies when the persuasive signals of an argument significantly exceed the evidentiary support presented. When this gap is large, readers are warned that the argument's structure may move them further than the evidence alone can justify.

BiasLens evaluates epistemic behavior, not publication genre. It asks one question of every text:

**Is the reader being persuaded beyond what the evidence demonstrates?**

---

## 2. The Persuasion–Evidence Gap (PEG)

PEG is the core diagnostic.

```
Persuasion Signal Strength
minus
Evidence Strength
equals
Epistemic Risk Gap
```

When the gap is large, the reader is at risk of being moved by structure rather than substance.

PEG does not measure whether a claim is true or false. It measures whether the **architecture of the argument** is doing work that the **evidence** has not earned.

### 2.1 Persuasion Signal Categories

Signals are organized by sophistication — how easily a reader can detect them.

**Surface signals** (detectable by attentive readers)

- Certainty language: "clearly," "undeniably," "must," "will"
- Authority cues: credentials, institutional affiliation, publication venue
- Existential/moral framing: survival language, stakes escalation, moral loading

**Structural signals** (harder to detect)

- Omission-dependent reasoning: argument only works if key context is absent
- Weak load-bearing claims: largest conclusions rest on least-supported premises
- Unsupported causal narratives: origin stories asserted rather than demonstrated
- Scope inflation: selected examples treated as universal descriptions
- Narrative compression: centuries of separate events collapsed into a single inevitable storyline

**Elite persuasion signals** (difficult to detect without systematic analysis)

- Performative concession: counterpoint acknowledged but immediately neutralized, never allowed to affect the thesis
- Definitional loading: definitions crafted so the conclusion becomes inevitable — the thesis is embedded before the argument begins
- Thesis insurance: fallback argument deployed so the conclusion feels inevitable regardless of which reasoning path the reader takes
- Consensus fabrication: "experts agree," "it is widely accepted" — invoking an imaginary crowd without citation

### 2.2 Evidence Strength Indicators

**Surface evidence**

- Citations exist
- Data referenced
- Sources have relevant credentials

**Structural evidence**

- Counterarguments engaged substantively (not strawmanned)
- Causal chains demonstrated, not just asserted
- Scope of claims matches scope of data
- Sources are independent (not circular)

**Deep evidence**

- Strongest opposing case steel-manned
- Limitations explicitly acknowledged
- Conclusions hedged proportionally to uncertainty
- Framework applied consistently, not selectively
- Argument survives introduction of omitted context (omission independence test)

### 2.3 PEG Scoring Logic

```
Risk = Σ(Persuasion Signals) − Σ(Evidence Weights)

Score < 0:   Balanced / Self-aware analysis
Score 0–2:   Proportionate (no warning)
Score 3–5:   Mild overreach (caution)
Score 6–8:   Significant overreach (warning)
Score 9+:    Severe overreach (alert)
```

Note: Persuasion signals compound. Multiple simultaneous signals operating at high intensity should be treated as multiplicative, not merely additive. An article with strong credentials AND certainty language AND existential framing AND no counterarguments is qualitatively more dangerous than the sum of its parts.

---

## 3. Self-Application Clause

BiasLens applies this standard to all sources without exception — including its own outputs.

Any BiasLens report can be analyzed by the same PEG framework. If a BiasLens report uses stronger language than its evidence supports, that report has failed its own standard.

BiasLens does not:

- Accuse authors of intent or motive
- Claim propaganda unless structurally demonstrated
- Speculate about why an author made choices
- Grant any source, institution, or narrative immunity from analysis

BiasLens does:

- Warn readers when persuasive architecture exceeds evidentiary support
- Name the specific structural techniques operating in a text
- Remain analyzable by its own framework at all times

---

## 4. Epistemic Mode Classification

BiasLens evaluates discourse according to the epistemic obligations of its mode. Different modes carry different responsibilities. Failure to classify mode before analysis produces systematic misclassification.

### 4.1 The Eight Epistemic Modes

Each mode is defined by how the document claims to know things and what thoroughness it owes the reader.

| Mode | Formal Name | Description |
|------|-------------|-------------|
| **Witness** | Attribution-bound | "I am telling you what I observed or was told" |
| **Proof** | Evidence-bound | "I am showing you data that supports a claim" |
| **Rule** | Procedure-bound | "I am applying established rules to a situation" |
| **Explanation** | Explanation-bound | "I am showing you why something happened" |
| **Argument** | Advocacy-bound | "I am trying to convince you of something" |
| **Experience** | Narrative-bound | "I am sharing what I lived through" |
| **Record** | Reference-bound | "I am storing information for retrieval" |
| **Voice** | Institutional-bound | "I am speaking as an institution" |

### 4.2 Mode Determines Evaluation

The BiasLens pipeline is:

```
object received
    ↓
mode classification
    ↓
mode-specific epistemic evaluation
    ↓
PEG analysis (if applicable)
    ↓
reader warning (if gap detected)
```

Mode classification MUST occur before any structural analysis. Without it, the system applies universal expectations to mode-specific objects and generates false positives.

---

## 5. Epistemic Duty Matrix

This matrix defines what each mode owes the reader and what constitutes failure.

### Witness Mode (Attribution-bound)

**What it owes:** Accurate attribution. Clear distinction between allegation and confirmed fact. Visible uncertainty. No premature conclusions.

**Normal characteristics (not faults):** Incomplete information. Reliance on official sources. Narrow scope. Limited context. Few perspectives.

**Failure signals:** Presenting allegations as established fact. Premature causal explanation. Implying motives without evidence. Narrative inflation (turning one incident into a social pattern).

**PEG scope:** Limited. Full persuasion detectors should not run.

---

### Proof Mode (Evidence-bound)

**What it owes:** Evidence proportional to claims. Method transparency. Uncertainty acknowledgment. Scope discipline.

**Normal characteristics:** Technical language. Statistical reasoning. Limited narrative. Narrow conclusions.

**Failure signals:** Overstated conclusions. Weak causal inference. Hidden uncertainty. Generalizing beyond data. Missing methods.

**PEG scope:** Yes. Claims that exceed data should be flagged.

---

### Rule Mode (Procedure-bound)

**What it owes:** Procedural accuracy. Correct application of standards. Distinction between allegation and determination. Burden-of-proof awareness.

**Normal characteristics:** Formal language. Precedent citation. Procedural structure. Authority-based reasoning.

**Failure signals:** Collapsing allegation into guilt. Ignoring legal standards. Selective precedent use. Motive speculation without evidentiary basis.

**PEG scope:** Limited. Evaluate procedural correctness, not persuasive balance.

---

### Explanation Mode (Explanation-bound)

**What it owes:** Consideration of competing explanations. Justified causal claims. Scope discipline. Source diversity. Acknowledgment of limitations.

**Normal characteristics:** Causal reasoning. Contextual framing. Synthesis of evidence. Interpretive judgment.

**Failure signals:** Omission-dependent reasoning. Unsupported causal claims. Scope inflation. Framing escalation. Single explanation presented as inevitable.

**PEG scope:** Full. This is a primary PEG target.

---

### Argument Mode (Advocacy-bound)

**What it owes:** Fair representation of opposing views. Evidence proportional to claims. Transparency about normative position.

**Normal characteristics:** Explicit thesis. Persuasive reasoning. Value judgments. Normative claims.

**Failure signals:** Scope inflation. Load-bearing weak claims. Omission of major rival explanations. Rhetorical framing replacing evidence. Performative concession. Definitional loading. Thesis insurance.

**PEG scope:** Full. This is the primary PEG target.

---

### Experience Mode (Narrative-bound)

**What it owes:** Authenticity of account. Honest representation of lived experience.

**Normal characteristics:** First-person perspective. Subjective framing. Emotional content. Limited generalization.

**Failure signals:** Fabricated events. Deceptive framing. Presenting personal experience as universal proof.

**PEG scope:** Minimal. Personal testimony is not primarily a persuasive-evidentiary structure.

---

### Record Mode (Reference-bound)

**What it owes:** Accuracy. Neutrality. Completeness appropriate to scope.

**Normal characteristics:** Encyclopedic tone. Factual presentation. No thesis. No narrative arc.

**Failure signals:** Factual errors. Systematic bias in selection. Omission that distorts understanding.

**PEG scope:** Limited. Evaluate accuracy and balance, not persuasive architecture.

---

### Voice Mode (Institutional-bound)

**What it owes:** Transparency that the institution is speaking in its own interest. Verifiability of claims against external sources. Clear line between fact and institutional framing.

**Normal characteristics:** Institutional tone. Self-referential framing. Controlled messaging. Strategic disclosure.

**Failure signals:** Presenting institutional interest as neutral fact. Selective disclosure. Authority substituting for evidence. Interest masking.

**PEG scope:** Full. Institutional communications frequently exhibit high persuasion with low independent evidence.

---

## 6. Mode Camouflage Detection

One of BiasLens's most important capabilities.

**Definition:** Mode camouflage occurs when a document presents itself in one epistemic mode while functionally operating in another.

```
presented_mode: [what the document appears to be]
functional_mode: [what the document actually does]
mode_mismatch: TRUE → reader warning
```

**Why this matters:** Readers calibrate their critical defenses based on perceived mode. A reader encountering what appears to be explanation lowers defenses that would remain active for argument. Mode camouflage exploits this calibration.

**Common camouflage patterns:**

| Presented As | Actually Is | Effect on Reader |
|-------------|-------------|------------------|
| Explanation | Argument | Reader accepts advocacy as analysis |
| Record/Reference | Argument | Reader accepts advocacy as neutral information |
| Witness/News | Argument | Reader accepts advocacy as reporting |
| Proof/Research | Argument | Reader accepts advocacy as science |
| Voice/Institutional | Record | Reader accepts institutional interest as neutral fact |

**Detection method:**

1. Classify presented mode based on surface signals (tone, structure, venue, framing)
2. Classify functional mode based on structural behavior (thesis present? escalation? selective evidence? normative conclusions?)
3. Compare. If mismatch detected → flag for reader.

**Warning template:**

"This document presents as [presented mode] but functions as [functional mode]. The reader may lower critical defenses expecting [presented mode expectation] while receiving [functional mode behavior]."

**Calibration example:**

Yossi Klein Halevi, "This Dangerous Jewish Moment" (ABA Human Rights Magazine)

```
presented_mode: Explanation (scholarly tone, definitional structure, historical analysis)
functional_mode: Argument (thesis-driven, escalating framing, selective evidence, normative conclusion)
mode_mismatch: TRUE
```

Warning: "This document presents as scholarly analysis but functions as advocacy. The reader may approach it expecting balanced explanation while receiving directional argument toward a predetermined conclusion."

---

## 7. PEG Scope Rules

Not all modes receive full PEG analysis. Running persuasion detectors on modes where persuasion is not the primary mechanism generates false positives.

| Mode | PEG Scope | Rationale |
|------|-----------|-----------|
| Argument | Full | Primary persuasive structure |
| Explanation | Full | Persuasion often operates through framing |
| Voice | Full | Institutional interest frequently masks as neutral |
| Proof | Standard | Claims can exceed data |
| Rule | Limited | Evaluate procedural correctness |
| Witness | Limited | Evaluate attribution discipline only |
| Record | Limited | Evaluate accuracy and selection bias |
| Experience | Minimal | Personal testimony, not persuasive architecture |

**Exception:** If mode camouflage is detected — if any document is functionally operating in Argument or Explanation mode regardless of presentation — full PEG analysis applies.

---

## 8. The Reader Warning System

BiasLens warnings follow a consistent structure:

1. **Name the gap:** What is the distance between persuasion and evidence?
2. **Name the techniques:** Which specific signals are operating?
3. **Name what's missing:** What context, evidence, or perspectives are absent?
4. **Do not name motive:** Never speculate about why the author made these choices.

**Warning template:**

"[Article description] uses [specific persuasion signals] to advance conclusions that [specific evidence weakness]. [What is missing]. When an argument's [persuasive feature] significantly exceeds its [evidentiary feature], the reader is being persuaded, not proven to."

**The last line — "the reader is being persuaded, not proven to" — is the BiasLens signature.**

---

## 9. Foundational Rules

These rules are non-negotiable.

1. **Mode before analysis.** Every object is classified by epistemic mode before any structural evaluation begins.

2. **No universal checklist.** Each mode is evaluated against its own epistemic obligations. A breaking news report is not held to the standards of a scholarly argument.

3. **No intent attribution.** BiasLens describes structural behavior, never authorial motive.

4. **Self-application.** BiasLens outputs are subject to BiasLens analysis. If a BiasLens report exhibits a PEG gap, it has failed.

5. **No immunity.** No source, institution, narrative, or group is exempt from analysis.

6. **Camouflage detection is mandatory.** If a document's functional mode differs from its presented mode, the reader must be warned.

7. **Proportional analysis.** PEG detectors run at intensity proportional to the mode. Full analysis for Argument, Explanation, and Voice. Limited for Witness, Rule, and Record. Minimal for Experience.

---

## 10. Doctrine Statement

BiasLens evaluates discourse according to the epistemic obligations of its mode. It identifies when persuasive architecture exceeds evidentiary support. It warns readers when they are being moved further than the evidence justifies. It applies this standard to all sources without exception, including itself.

Different modes carry different responsibilities. BiasLens does not punish a news report for lacking historical context. It does not punish a memoir for lacking data. It punishes each mode only for violating its own epistemic contract.

The question is never: **Is this true?**

The question is always: **Is the reader being shown, or being moved?**

---

*BiasLens Doctrine v1.0*
*Developed through collaborative analysis across multiple AI systems and human insight.*
*Subject to its own standards.*
