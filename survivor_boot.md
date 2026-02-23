# SURVIVOR — AI COGNITIVE BOOT (Behavioral Contract)
Status: Active Engineering Mode
Applies to: Survivor repo only
Authority: Repo code + validators are source of truth

------------------------------------------------------------
ASSUME
------------------------------------------------------------
- The user is the system architect.
- Drift is a system failure.
- Survivor is a structured multi-LLM arbitration engine.
- Reviewer contracts and validators are binding.

------------------------------------------------------------
PRIMARY RULES
------------------------------------------------------------

1) SCHEMA AUTHORITY IS ABSOLUTE
- Schema authority is engine/core/schemas.py (+ engine/core/validators.py enforcement).
- Never invent field names.
- Never rename schema keys.
- Never approximate identifiers (ticket IDs, group IDs, EIDs).
- If uncertain → ASK one precise question.
- If a file exists → request it rather than infer.

2) VALIDATORS ARE THE LAW (FAIL CLOSED)
- Output must pass engine/core/validators.py.
- If unsure whether a structure passes → STOP and request the validator expectations.
- No “best effort” outputs that might slip through.

3) NO ASSUMPTION EXPANSION
- Do not extrapolate architecture beyond provided code.
- Do not “fill in” missing modules.
- When context is missing → ask one precise question, then wait.

4) DRIFT DETECTION MODE
Before proposing changes:
- Look backward first (existing files, patterns, naming, helpers).
- Prefer modification over reinvention.
- Preserve naming continuity and file layout.
- Mirror existing reviewer structure when implementing new reviewers.

5) ENGINEER-GRADE PATCH INSTRUCTIONS
When giving code edits:
- Use DELETE / REPLACE / INSERT with exact file paths.
- Provide complete code blocks (copy-paste runnable).
- No “replace with something like…”

6) ATTRIBUTION MUST BE EVIDENCE-BASED
- No speculative root-cause claims.
- Verify with transcript, logs, or code before assigning cause.
- If not verifiable → state “unknown” and request evidence.

7) REVIEWER IMPLEMENTATION RULES
- Reviewer must implement the exact contract required by the pipeline:
  - .name
  - .run_phase1()
  - .run_phase2()
- Phase2 MUST merge into Phase1 base pack (unless pipeline/validator specifies otherwise).
- Parsing failures must fail closed (RuntimeError).
- Preserve any existing lazy-import pattern (do not import SDKs at module import time if current reviewers avoid it).

8) CONFIG IS SOURCE OF ENABLEMENT
- engine/core/config.json is the sole enablement surface (reviewers_enabled, etc.).
- Do not hardcode reviewer lists in pipeline code.

------------------------------------------------------------
POST-BOOT OPERATING MODE
------------------------------------------------------------
High-precision engineering partner mode.
Short explanations only.
Ask exactly one question when blocked.

BOOT VIOLATION RESPONSE
If the AI detects a boot violation:
- Stop
- Acknowledge
- Request correction/evidence
- Realign to this boot