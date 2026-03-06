#!/usr/bin/env python3
"""
FILE: engine/reviewers/claude_reviewer.py
VERSION: 0.1
PURPOSE:
Claude (Anthropic) reviewer adapter for Survivor.

CONTRACT:
- Must expose class ClaudeReviewer with .name, .run_phase1(), .run_phase2()
- Must return a ReviewerPack dict that passes engine/core/validators.py
- Must fail closed (RuntimeError) on SDK/key/parse errors.

NOTES:
- Mirrors engine/reviewers/openai_reviewer.py structure.
- Uses anthropic SDK: anthropic.Anthropic(api_key=...).messages.create(...)
- Enforces globally-unique claim_id values by prefixing with "<reviewer>-".
"""

from __future__ import annotations

import json
from typing import Any, Dict

from engine.core.triage_utils import list_triage_claims
from engine.reviewers.base import ReviewerInputs
from engine.prompts.builder import build_system_prompt


class ClaudeReviewer:
    def __init__(self, name: str = "claude", model: str = "claude-sonnet-4-6") -> None:
        self.name = name
        self.model = model

    # ----------------------------
    # Anthropic client + key loading
    # ----------------------------
    def _get_client(self):
        # Lazy import so pipeline doesn't crash until this reviewer is selected.
        try:
            import anthropic  # type: ignore
        except Exception as e:
            raise RuntimeError(f"anthropic SDK not installed or failed to import: {e}")

        # Prefer Survivor's env loader; fail closed if missing.
        try:
            from engine.core.env import get_claude_key  # type: ignore
            api_key = get_claude_key()
        except Exception:
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found. Put it in .env and ensure it is loaded.")

        try:
            return anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Failed to create Anthropic client: {e}")

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
    # Prompts (mirror OpenAIReviewer)
    # ----------------------------
    def _phase1_prompt(self, inp: ReviewerInputs) -> str:
        return f"""
You are an epistemic integrity reviewer. Return ONLY valid JSON.

You must output a single object with these keys exactly:
- reviewer (string)
- whole_article_judgment (object: classification, confidence, evidence_eids)
- main_conclusion (object: text, evidence_eids, confidence)
- claims (list of objects: claim_id, text, type, evidence_eids, centrality)
- scope_markers (list of objects: text, marker_type, evidence_eids)
- causal_links (list of objects: from_claim_id, to_claim_id, evidence_eids)
- article_patterns (list of objects: pattern_type, evidence_eids)
- omission_candidates (list of objects: missing_frame, reason_expected, confidence)
- counterfactual_requirements (list of objects: target_claim_id, counterfactual_type, measurable_type, description, why_it_changes_confidence, confidence)
- evidence_density (object: claims_count, claims_with_internal_support, external_sources_count)
- claim_tickets (list)
- article_tickets (list)
- cross_claim_votes (list)  # MUST be [] in Phase 1

Hard rules:
- evidence_eids must ONLY reference eids that exist in the provided EvidenceBank.
- confidence must be one of: low, medium, high.
- classification must be a short label like: reporting, analysis, advocacy, uncertain.
- If uncertain, evidence_eids may be [].

Reviewer name: {self.name}

EVIDENCEBANK (authoritative):
{json.dumps(inp.evidence_bank, indent=2)}

ARTICLE (normalized text):
{inp.normalized_text}
""".strip()

    def _phase2_prompt(self, inp: ReviewerInputs, cross_payload: Dict[str, Any]) -> str:
        phase1_outputs = cross_payload.get("phase1_outputs", {})
        if not isinstance(phase1_outputs, dict):
            raise RuntimeError("cross_review_payload.phase1_outputs must be dict")

        claim_index: Dict[str, Dict[str, Any]] = {}
        for _m, pack in phase1_outputs.items():
            for c in list_triage_claims(pack):
                claim_index[c["claim_id"]] = c

        max_nd = int(inp.config.get("max_near_duplicate_links", 3))

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
- near_duplicate_of (optional list[str], max {max_nd})

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
        client = self._get_client()

        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:
            raise RuntimeError(f"Anthropic call failed: {e}")

        # Anthropic returns a list of content blocks; join all text blocks.
        if not resp or not getattr(resp, "content", None):
            raise RuntimeError("Anthropic returned empty response content")

        parts = []
        for b in resp.content:
            t = getattr(b, "text", None)
            if isinstance(t, str) and t.strip():
                parts.append(t)

        content = "\n".join(parts).strip()
        if not content:
            raise RuntimeError("Anthropic returned empty text blocks")

        # ---- normalize fenced JSON / stray preamble ----
        s = content.strip()

        # Strip ```json ... ``` fences (Claude often wraps despite instruction)
        if s.startswith("```"):
            lines = s.splitlines()
            # drop first fence line (``` or ```json)
            if lines:
                lines = lines[1:]
            # drop trailing fence
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines).strip()

        # If still not starting with '{', try extracting outermost JSON object.
        if not s.startswith("{"):
            l = s.find("{")
            r = s.rfind("}")
            if l == -1 or r == -1 or r <= l:
                raise RuntimeError(f"Anthropic returned non-JSON content:\n{content}")
            s = s[l : r + 1]

        try:
            data = json.loads(s)
        except Exception as e:
            raise RuntimeError(f"Failed to parse Anthropic JSON: {e}\nRaw content:\n{content}")

        if not isinstance(data, dict):
            raise RuntimeError("Anthropic JSON root must be an object/dict")

        return data

    # ----------------------------
    # Public API
    # ----------------------------
    def run_phase1(self, inp: ReviewerInputs) -> Dict[str, Any]:
        gsae_enabled = inp.config.get("gsae_settings", {}).get("enabled") is True
        system_prompt = build_system_prompt("judge", "machine", include_gsae=gsae_enabled)
        out = self._call_json(system_prompt, self._phase1_prompt(inp))
        out["reviewer"] = self.name
        out["cross_claim_votes"] = []  # Phase 1 must be empty list
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
        }

        for k, v in phase2_out.items():
            if k in allowed_overrides or k == "reviewer":
                merged[k] = v

        merged["reviewer"] = self.name

        if "cross_claim_votes" not in merged:
            merged["cross_claim_votes"] = my_phase1.get("cross_claim_votes", [])

        # Ensure claim ids stay prefixed if Phase2 re-emits claims
        merged = self._prefix_claim_ids(merged)

        return merged
