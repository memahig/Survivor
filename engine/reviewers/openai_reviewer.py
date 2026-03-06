#!/usr/bin/env python3
"""
FILE: engine/reviewers/openai_reviewer.py
VERSION: 0.1
PURPOSE:
OpenAI-backed Reviewer implementation for Survivor.

CONTRACT:
- Must expose class OpenAIReviewer with .name, .run_phase1(), .run_phase2()
- Must return a ReviewerPack dict that passes engine/core/validators.py
- Must not crash if OpenAI is unavailable; should fail clearly (RuntimeError)

NOTES:
- v0.1 is deliberately simple:
  - Phase 1: ask for structured JSON ReviewerPack (without cross-claim votes)
  - Phase 2: ask for cross-claim votes against shared claim index (from phase1_outputs)
- If parsing fails, fail closed (RuntimeError).
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from engine.core.triage_utils import list_triage_claims
from engine.reviewers.base import ReviewerInputs
from engine.prompts.builder import build_system_prompt


class OpenAIReviewer:
    def __init__(self, name: str = "openai", model: str = "gpt-4o-mini") -> None:
        self.name = name
        self.model = model

    # ----------------------------
    # OpenAI client + key loading
    # ----------------------------
    def _get_openai_client(self):
        # Lazy import so pipeline doesn't crash until this reviewer is selected.
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError(f"OpenAI SDK not installed or failed to import: {e}")

        # Prefer Survivor's env loader; fail closed if missing.
        try:
            from engine.core.env import get_openai_key  # type: ignore
            api_key = get_openai_key()
        except Exception:
            import os
            api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found. Put it in .env and ensure it is loaded.")

        return OpenAI(api_key=api_key)

    # ----------------------------
    # Prompts
    # ----------------------------
    def _phase1_prompt(self, inp: ReviewerInputs) -> str:
        max_pillar = int(inp.config.get("max_pillar_claims_per_reviewer", 10))
        max_quest = int(inp.config.get("max_questionable_claims_per_reviewer", 15))
        max_omit = int(inp.config.get("max_omission_candidates", 5))
        max_cf = int(inp.config.get("max_counterfactuals", 5))
        return f"""
You are an epistemic integrity reviewer. Return ONLY valid JSON — no markdown, no text before or after.
Never cut off JSON. Always return a complete, closed JSON object.

HARD CONSTRAINTS — violations cause rejection:
- type MUST be one of: factual, causal, normative, predictive. Nothing else. Default: factual.
- centrality MUST be an integer: 1, 2, or 3. Not a word. Default: 2.
- confidence MUST be: low, medium, or high.
- classification MUST be: reporting, analysis, advocacy, mixed, or uncertain.
- evidence_eids MUST only reference eids from the EvidenceBank below.
- pillar_claims: max {max_pillar} items. IDs: PC1, PC2, ...
- questionable_claims: max {max_quest} items. IDs: QC1, QC2, ...
- omission_candidates: max {max_omit} items.
- counterfactual_requirements: max {max_cf} items.
- cross_claim_votes MUST be [] in Phase 1.
- claim text: under 120 characters. No full sentences — use fragments.
- missing_frame: under 80 characters.
- reason_expected: under 20 words.
- description: under 25 words.
- why_it_changes_confidence: under 20 words.
- If output grows large, CUT LIST LENGTHS rather than risk truncation.
- Prefer fewer, higher-quality items. Use [] for any list with no strong items.

EXAMPLE of correct claim format:
{{"claim_id": "PC1", "text": "Claim under 120 chars", "type": "factual", "evidence_eids": ["E1"], "centrality": 2}}

OBJECT LOCK — analyze the provided article only:
- Do not discuss the broader topic, provide background education, or offer moral commentary.
- Answer only: "how is this article constructing its argument?"
- If a finding is not grounded in the article text or EvidenceBank, do not include it.
- Never infer author intent or motive. Report structure, not psychology.

OMISSION DETECTION — test at 3 levels:
1. CLAIM-LEVEL: For each pillar claim, what rival context is normally expected but absent?
2. ARTICLE-LEVEL: For the main conclusion, what major rival explanations are missing?
3. FRAMING-LEVEL: How does the article define the problem? What alternative framings are excluded?

STRUCTURAL FINDINGS to detect (use in article_patterns):
- scope_inflation (selected examples treated as universal)
- unsupported_causal_or_origin_story (causal claims asserted without evidence)
- omission_dependent_reasoning (argument works because alternatives absent)
- framing_escalation (gradual shift from analysis to survival/threat framing)
- load_bearing_weakness (biggest conclusions rest on weakest claims)

REQUIRED KEYS (must all be present):
reviewer, whole_article_judgment, main_conclusion, pillar_claims, questionable_claims,
background_claims_summary, scope_markers, causal_links, article_patterns,
omission_candidates, counterfactual_requirements, evidence_density,
claim_tickets, article_tickets, cross_claim_votes

OPTIONAL KEYS (include when findings exist):
claim_omissions, article_omissions, framing_omissions, argument_summary, object_discipline_check

Required key shapes:
- whole_article_judgment: {{classification, confidence, evidence_eids}}
- main_conclusion: {{text, evidence_eids, confidence}}
- background_claims_summary: {{total_claims_estimate: int, not_triaged_count: int}}
- evidence_density: {{claims_count, claims_with_internal_support, external_sources_count}}
- scope_markers: [{{text, marker_type, evidence_eids}}]
- causal_links: [{{from_claim_id, to_claim_id, evidence_eids}}]
- article_patterns: [{{pattern_type, evidence_eids}}]
- omission_candidates: [{{missing_frame, reason_expected, confidence}}]
- counterfactual_requirements: [{{target_claim_id, counterfactual_type, measurable_type, description, why_it_changes_confidence, confidence}}]

Optional key shapes:
- claim_omissions: [{{target_claim_id, missing_frame, reason_expected, confidence}}]
- article_omissions: [{{missing_frame, affected_claim_ids, reason_expected, confidence}}]
- framing_omissions: [{{frame_used_by_article, missing_frame, alternative_frames: [str], reason_expected, confidence}}]
- argument_summary: {{main_conclusion: str, supporting_reasons: [str], key_rival_explanations_missing: [str]}}
- object_discipline_check: {{status: "pass"|"fail", reason: str}}

Keep all lists sparse — fewer high-quality items over exhaustive lists.
Do not explain reasoning — just state the claim or finding.

Reviewer name: {self.name}

EVIDENCEBANK (authoritative):
{json.dumps(inp.evidence_bank, indent=2)}

ARTICLE (normalized text):
{inp.normalized_text}
""".strip()

    def _phase2_prompt(self, inp: ReviewerInputs, cross_payload: Dict[str, Any]) -> str:
        # In v0: only require cross_claim_votes to be filled; other fields can be copied.
        phase1_outputs = cross_payload.get("phase1_outputs", {})
        if not isinstance(phase1_outputs, dict):
            raise RuntimeError("cross_review_payload.phase1_outputs must be dict")

        # Build a simple claim index for the model to vote on.
        claim_index: Dict[str, Dict[str, Any]] = {}
        for _m, pack in phase1_outputs.items():
            for c in list_triage_claims(pack):
                claim_index[c["claim_id"]] = c

        return f"""
You are performing Phase 2 cross-review voting. Return ONLY valid JSON.

You must output a single object with the SAME keys as Phase 1, BUT:
- cross_claim_votes MUST be a list of votes, one per claim_id in the claim index.
Each entry:
- claim_id (string)
- exists_as_real_claim (bool)
- is_material_to_argument (bool)
- vote (one of: supported, unsupported, undetermined)
- confidence (low|medium|high)
- centrality (1|2|3)
- near_duplicate_of (optional list[str], max {int(inp.config.get("max_near_duplicate_links", 3))})

Hard rules:
- evidence_eids must ONLY reference eids that exist in the provided EvidenceBank.
- If you include near_duplicate_of, only point to claim_ids that exist in the claim index.

Reviewer name: {self.name}

EVIDENCEBANK (authoritative):
{json.dumps(inp.evidence_bank, indent=2)}

CLAIM INDEX (cross-review target set):
{json.dumps(claim_index, indent=2)}

ARTICLE (normalized text):
{inp.normalized_text}
""".strip()

    # ----------------------------
    # JSON call helper
    # ----------------------------
    def _call_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        client = self._get_openai_client()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI call failed: {e}")

        content = resp.choices[0].message.content if resp and resp.choices else None
        if not content or not isinstance(content, str):
            raise RuntimeError("OpenAI returned empty response content")

        # ---- diagnostic: log output size before parse ----
        finish = resp.choices[0].finish_reason if resp.choices else None
        print(
            f"[{self.name}] raw output: {len(content)} chars, "
            f"{len(content.splitlines())} lines, finish_reason={finish}",
            file=sys.stderr,
        )

        try:
            data = json.loads(content)
        except Exception as e:
            raise RuntimeError(f"Failed to parse OpenAI JSON: {e}\nRaw content:\n{content}")

        if not isinstance(data, dict):
            raise RuntimeError("OpenAI JSON root must be an object/dict")

        # ---- diagnostic: section item counts ----
        _diag_parts = []
        for _dk in ("pillar_claims", "questionable_claims", "omission_candidates",
                     "counterfactual_requirements", "cross_claim_votes"):
            _dv = data.get(_dk)
            if isinstance(_dv, list):
                _diag_parts.append(f"{_dk}={len(_dv)}")
        if _diag_parts:
            print(f"[{self.name}] sections: {', '.join(_diag_parts)}", file=sys.stderr)

        return data

    # ----------------------------
    # Claim-id normalization
    # ----------------------------
    def _prefix_claim_ids(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure claim_id values are globally unique by prefixing with reviewer name
        unless they already start with '<name>-'.

        Also rewrites references in:
          - causal_links (from_claim_id/to_claim_id)
          - counterfactual_requirements (target_claim_id)
          - cross_claim_votes (claim_id, near_duplicate_of)
        """
        all_claims = list_triage_claims(pack)
        if not all_claims:
            return pack

        id_map: Dict[str, str] = {}
        for c in all_claims:
            if not isinstance(c, dict):
                continue
            cid = c.get("claim_id")
            if not isinstance(cid, str) or not cid:
                continue

            if cid.startswith(f"{self.name}-"):
                id_map[cid] = cid
                continue

            new_id = f"{self.name}-{cid}"
            id_map[cid] = new_id
            c["claim_id"] = new_id

        def _remap(x: Any) -> Any:
            if isinstance(x, str):
                return id_map.get(x, x)
            if isinstance(x, list):
                return [_remap(i) for i in x]
            if isinstance(x, dict):
                return {k: _remap(v) for k, v in x.items()}
            return x

        if "causal_links" in pack:
            pack["causal_links"] = _remap(pack["causal_links"])
        if "counterfactual_requirements" in pack:
            pack["counterfactual_requirements"] = _remap(pack["counterfactual_requirements"])
        if "cross_claim_votes" in pack:
            pack["cross_claim_votes"] = _remap(pack["cross_claim_votes"])

        return pack

    # ----------------------------
    # Public API
    # ----------------------------
    def run_phase1(self, inp: ReviewerInputs) -> Dict[str, Any]:
        gsae_enabled = inp.config.get("gsae_settings", {}).get("enabled") is True
        system_prompt = build_system_prompt("judge", "machine", include_gsae=gsae_enabled)
        out = self._call_json(system_prompt, self._phase1_prompt(inp))

        # Enforce reviewer name + Phase1 invariant
        out["reviewer"] = self.name
        out["cross_claim_votes"] = []
        out = self._prefix_claim_ids(out)
        return out

    def run_phase2(self, inp: ReviewerInputs, cross_review_payload: Dict[str, Any]) -> Dict[str, Any]:
        phase1_all = cross_review_payload["phase1_outputs"]
        my_phase1 = phase1_all[self.name]

        gsae_enabled = inp.config.get("gsae_settings", {}).get("enabled") is True
        system_prompt = build_system_prompt("judge", "machine", include_gsae=gsae_enabled)
        phase2_out = self._call_json(system_prompt, self._phase2_prompt(inp, cross_review_payload))

        if not isinstance(phase2_out, dict):
            raise RuntimeError(f"{self.name} Phase2 returned non-dict: {type(phase2_out)}")

        # START FROM PHASE1 PACK (complete ReviewerPack) and overlay Phase2 deltas
        merged = dict(my_phase1)

        # Only allow Phase2 to override/extend specific keys (fail-closed-ish)
        allowed_overrides = {
            "cross_claim_votes",
            "article_tickets",
            "claim_tickets",
            "counterfactual_requirements",
            "article_patterns",
            "omission_candidates",
            "causal_links",
            "scope_markers",
            "pillar_claims",
            "questionable_claims",
            "background_claims_summary",
            "main_conclusion",
            "whole_article_judgment",
            "evidence_density",
            "claim_omissions",
            "article_omissions",
            "framing_omissions",
            "argument_summary",
            "object_discipline_check",
        }

        for k, v in phase2_out.items():
            if k in allowed_overrides or k == "reviewer":
                merged[k] = v

        # Always enforce reviewer name
        merged["reviewer"] = self.name

        if "cross_claim_votes" not in merged:
            merged["cross_claim_votes"] = my_phase1.get("cross_claim_votes", [])

        # Ensure claim IDs stay prefixed if Phase2 re-emits claims
        merged = self._prefix_claim_ids(merged)

        return merged