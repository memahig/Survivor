# SURVIVOR — SESSION_STATE.md
DATE: 2026-02-22
PROJECT: Survivor
PHASE: Engine bring-up / multi-reviewer wiring stabilization
STATUS: ✅ Pipeline runs end-to-end with OpenAI + Gemini + Mock Claude

------------------------------------------------------------
PRIMARY OUTCOME
------------------------------------------------------------
Survivor pipeline now executes successfully end-to-end:
Ingest → Normalize → EvidenceBank → Phase1 → Cross-Review → Phase2 →
Adjudication → Validation → Render (report.md + debug.md + run.json + tickets.json)

Artifacts confirmed written to out/:
- debug.md
- phase2_outputs.json
- report.md
- run.json
- tickets.json

------------------------------------------------------------
GEMINI INTEGRATION (KEY EVENTS)
------------------------------------------------------------
1) google.generativeai deprecated → migrated to google-genai (google.genai).
2) Encountered API key issues:
   - 403 PERMISSION_DENIED “API key reported as leaked” → generated a new key.
   - 400 INVALID_ARGUMENT “API key not valid” → corrected key placement/loading.
   - 429 quota errors → billing/plan adjustments.
   - 404 model availability: gemini-2.0-flash not available to new users → updated default model to gemini-2.5-flash.
3) Gemini is now producing Phase2 cross_claim_votes successfully.

Security note:
- DO NOT print or log API keys (confirmed).

------------------------------------------------------------
REVIEWER WIRING & IDENTITIES (IMPORTANT LOCK)
------------------------------------------------------------
Config now controls expected reviewers:
engine/core/config.json
  "reviewers_enabled": ["openai", "gemini", "mock_claude"]

Pipeline phase2 keys now match config reviewers_enabled:
- phase2 keys: ['openai', 'gemini', 'mock_claude']

No Claude SDK installed (anthropic not present) and no Claude API key.
Claude remains mock_claude for now.

------------------------------------------------------------
CLAIM ID UNIQUENESS FIX (CRITICAL)
------------------------------------------------------------
Problem:
- Adjudicator required globally unique claim_id across reviewers.
- Collision observed (e.g., Gemini emitted "C1" and another reviewer also emitted "C1").

Fix:
- Implemented claim_id prefixing for Gemini (and then OpenAI as well).
- Verified with run.json: all claim_ids unique.

Example result:
- openai-C1
- gemini-C1
- mock_claude-CL-01
- mock_claude-CL-02

Also ensured references are rewritten consistently when prefixing:
- causal_links (from_claim_id/to_claim_id)
- counterfactual_requirements (target_claim_id)
- cross_claim_votes (claim_id, near_duplicate_of)

------------------------------------------------------------
VALIDATION & RENDERING UPGRADES
------------------------------------------------------------
Validators:
- validate_run now requires reviewers based on config.reviewers_enabled
  (not hardcoded openai/gemini/claude).
- Still fail-closed.
- EID integrity enforcement remains (no phantom evidence_eids).

Renderer (engine/render/report.py):
- Updated to iterate over sorted(phase2.keys()) everywhere instead of hardcoding reviewers.
- Added "Disagreement Radar" section driven by claim-group tallies.
- Disagreement score now uses adjudicator tally keys:
  supported_votes / unsupported_votes / undetermined_votes
- Vote line renders per reviewer using reviewer_votes[model].vote when dict.

------------------------------------------------------------
CURRENT “KNOWN GOOD” TEST COMMANDS
------------------------------------------------------------
Run:
python3 scripts/run_survivor.py --textfile engine/tests/fixtures/sample_article.txt --outdir out

Inspect:
python -c "import json; d=json.load(open('out/run.json')); print('phase2 keys:', list(d['phase2'].keys()))"
python -c "import json; d=json.load(open('out/run.json')); ids=[]; [ids.extend([c.get('claim_id') for c in d['phase2'][m].get('claims',[]) if isinstance(c,dict)]) for m in d['phase2'].keys()]; ids=[i for i in ids if isinstance(i,str)]; print('unique_claim_ids:', len(set(ids)), 'total:', len(ids))"
grep -n "Reviewer Whole-Article Judgments" -n -A20 out/report.md

------------------------------------------------------------
OPEN ITEMS / NEXT STEPS
------------------------------------------------------------
1) Consider normalizing “model_weights” handling for mock reviewers:
   - Ensure adjudicator weight lookup matches reviewer names in phase2
   - Keep fail-closed behavior where appropriate, but avoid “Unknown model” surprises.

2) Decide how we want to treat "mock_*" names long-term:
   - Option A: keep reviewer.name as "mock_claude" everywhere (current).
   - Option B: keep reviewer.name as "claude" but mark as mock via metadata.
   (Current system uses reviewer.name directly as the key in phase outputs.)

3) Optional: add a tiny “run header” section into report.md:
   - reviewers_enabled list
   - model versions / selected models
   - config snapshot hash or excerpt

------------------------------------------------------------
DO-NOT-DO (GUARDS)
------------------------------------------------------------
- Do not print API keys.
- Do not hardcode reviewer lists in renderer or validators (must be config-driven).
- Claim IDs must remain globally unique across reviewers (keep prefixing).