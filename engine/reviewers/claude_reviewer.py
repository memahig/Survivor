#!/usr/bin/env python3
"""
FILE: engine/reviewers/claude_reviewer.py
VERSION: 0.2
PURPOSE:
Claude (Anthropic) reviewer adapter for Survivor.

CONTRACT:
- Must expose class ClaudeReviewer with .name, .run_phase1(), .run_phase2()
- Must return a ReviewerPack dict that passes engine/core/validators.py
- Must fail closed (RuntimeError) on SDK/key/parse errors.

v0.2 CHANGE:
- Two-pass Phase 1: skeletal triage (core fields) + enrichment (forensics).
  Prevents JSON truncation and streaming timeouts from monolithic prompts.
- Uses streaming API for both passes.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List

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
        try:
            import anthropic  # type: ignore
        except Exception as e:
            raise RuntimeError(f"anthropic SDK not installed or failed to import: {e}")

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

        for key in ("causal_links", "counterfactual_requirements", "cross_claim_votes",
                     "claim_omissions"):
            if key in pack:
                pack[key] = _remap(pack[key])

        return pack

    # ----------------------------
    # Pass 1: Skeletal triage prompt
    # ----------------------------
    def _triage_prompt(self, inp: ReviewerInputs) -> str:
        max_pillar = int(inp.config.get("max_pillar_claims_per_reviewer", 10))
        max_quest = int(inp.config.get("max_questionable_claims_per_reviewer", 15))
        return f"""
You are an epistemic integrity reviewer. Return ONLY valid JSON — no markdown, no text.
Never cut off JSON. Always return a complete, closed JSON object.

HARD CONSTRAINTS — violations cause rejection:
- type MUST be one of: factual, causal, normative, predictive. Default: factual.
- centrality MUST be an integer: 1, 2, or 3. Default: 2.
- confidence MUST be: low, medium, or high.
- classification MUST be: reporting, analysis, advocacy, mixed, or uncertain.
- evidence_eids MUST only reference eids from the EvidenceBank below.
- pillar_claims: max {max_pillar} items. IDs: PC1, PC2, ...
- questionable_claims: max {max_quest} items. IDs: QC1, QC2, ...
- cross_claim_votes MUST be [] in this pass.
- claim text: under 120 characters. No full sentences — use fragments.

EXAMPLE of correct claim format:
{{"claim_id": "PC1", "text": "Claim under 120 chars", "type": "factual", "evidence_eids": ["E1"], "centrality": 2}}

OBJECT LOCK — analyze the provided article only:
- Do not discuss the broader topic, provide background education, or offer moral commentary.
- Answer only: "how is this article constructing its argument?"
- Never infer author intent or motive. Report structure, not psychology.

STRICT SCHEMA — output ONLY these keys, nothing else:
Do not output integrity_assessment or any key not listed below.
Any extra key causes immediate rejection.

REQUIRED KEYS (must all be present):
reviewer, whole_article_judgment, main_conclusion, pillar_claims, questionable_claims,
background_claims_summary, evidence_density, claim_tickets, article_tickets, cross_claim_votes

Key shapes:
- whole_article_judgment: {{classification, confidence, evidence_eids}}
- main_conclusion: {{text, evidence_eids, confidence}}
- background_claims_summary: {{total_claims_estimate: int, not_triaged_count: int}}
- evidence_density: {{claims_count, claims_with_internal_support, external_sources_count}}
- claim_tickets: [] (empty for now)
- article_tickets: [] (empty for now)
- cross_claim_votes: [] (always empty in this pass)

Prefer fewer, higher-quality claims. Use [] for any list with no strong items.
Do not explain reasoning — just state the claim or finding.

Reviewer name: {self.name}

EVIDENCEBANK (authoritative):
{json.dumps(inp.evidence_bank, indent=2)}

ARTICLE (normalized text):
{inp.normalized_text}
""".strip()

    # ----------------------------
    # Pass 2: Enrichment prompt
    # ----------------------------
    def _enrichment_prompt(self, inp: ReviewerInputs, spine: Dict[str, Any]) -> str:
        max_omit = int(inp.config.get("max_omission_candidates", 5))
        max_cf = int(inp.config.get("max_counterfactuals", 5))
        max_rivals = int(inp.config.get("max_rival_narratives", 3))

        # Spine is the cross-reviewer merged argument skeleton
        pillar_claims = spine.get("pillar_claims", [])
        main_conclusion = spine.get("main_conclusion", {})

        return f"""
You are an epistemic integrity reviewer performing structural enrichment.
Return ONLY valid JSON — no markdown, no text before or after.
Never cut off JSON. Always return a complete, closed JSON object.

You already triaged this article. Now analyze its structural features.

HARD CONSTRAINTS:
- confidence MUST be: low, medium, or high.
- evidence_eids MUST only reference eids from the EvidenceBank below.
- omission_candidates: max {max_omit} items.
- counterfactual_requirements: max {max_cf} items.
- missing_frame: under 80 characters.
- reason_expected: under 20 words.
- description: under 25 words.
- why_it_changes_confidence: under 20 words.
- Prefer fewer, higher-quality items. Use [] for any list with no strong items.

OBJECT LOCK — analyze the provided article only:
- Do not discuss the broader topic, provide background education, or offer moral commentary.
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

RIVAL NARRATIVE TEST:
Construct at least one concrete rival narrative that fits the same core facts
but uses a different primary explanatory lens.
Then test whether the article's main conclusion survives if that rival narrative
is taken seriously.

For each rival narrative:
- rival_narrative_id: RN1, RN2, ...
- lens: name the alternative explanatory frame (under 10 words)
- summary: 1-2 sentences, under 120 chars
- same_core_facts_used: evidence_eids from EvidenceBank that the rival also explains
- claims_weakened_if_true: claim_ids from the spine that weaken or collapse
- structural_fragility: low (article survives), elevated (article weakened), high (article collapses)
- confidence: low, medium, or high

Do not infer intent. Do not defend the rival narrative as true.
Test whether the article's argument depends on excluding it.
Max rival narratives: {max_rivals}

ARGUMENT INTEGRITY TEST:
Reassemble the article's overall argument.
Identify:
- main_conclusion: the article's final or strongest overall conclusion
- load_bearing_claim_ids: claim_ids from the spine necessary for that conclusion
- weak_link_claim_ids: load-bearing claims that are weak, omission-dependent, overgeneralized, or structurally fragile
- support_chain_summary: 2-4 short lines describing how the conclusion is built
- argument_fragility: low (conclusion mostly survives), elevated (weakens materially), high (collapses or requires major revision)
- reason: one short sentence explaining the fragility rating
Evaluate the assembled argument, not just individual claims.
Ask whether the conclusion still stands if weak links are removed or rival narratives are admitted.
Do not infer intent. Analyze the structure of the provided article only.

REQUIRED KEYS (must all be present):
scope_markers, causal_links, article_patterns, omission_candidates, counterfactual_requirements

OPTIONAL KEYS (include when findings exist):
claim_omissions, article_omissions, framing_omissions, argument_summary, object_discipline_check, rival_narratives, argument_integrity

Required key shapes:
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
- rival_narratives: [{{rival_narrative_id, lens, summary, same_core_facts_used: [str], claims_weakened_if_true: [str], structural_fragility: "low"|"elevated"|"high", confidence}}]
- argument_integrity: {{main_conclusion: str, load_bearing_claim_ids: [str], weak_link_claim_ids: [str], support_chain_summary: [str], argument_fragility: "low"|"elevated"|"high", reason: str}}

MERGED ARGUMENT SPINE (from all reviewers' triage):
Main conclusion: {json.dumps(main_conclusion)}
Pillar claims (cross-reviewer): {json.dumps(pillar_claims, indent=2)}

Reviewer name: {self.name}

EVIDENCEBANK (authoritative):
{json.dumps(inp.evidence_bank, indent=2)}

ARTICLE (normalized text):
{inp.normalized_text}
""".strip()

    # ----------------------------
    # Phase 2 (cross-review) prompt
    # ----------------------------
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
    # TODO(EXIT-RAMP / PROVIDER PARITY): TEMPORARY CLAUDE-SPECIFIC RELIABILITY PATCH
    # -------------------------------------------------------------------------------
    # This retry/backoff logic exists only because Anthropic streaming currently
    # drops reviewer runs intermittently.  This must NOT become the long-term pattern
    # for provider integration.
    #
    # Future direction:
    # 1. Move retry/backoff policy into a provider-agnostic reviewer transport layer.
    # 2. Apply the same reliability contract across all providers.
    # 3. Keep provider-specific exceptions mapped at the adapter boundary only.
    # 4. Preserve exit ramps: no provider-specific assumptions may leak into core
    #    schema, adjudication, PEG, EMS, or report logic.
    #
    # DO NOT REMOVE THIS NOTE until a shared transport/retry abstraction exists.
    # -------------------------------------------------------------------------------
    def _call_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 16384) -> Dict[str, Any]:
        from engine.reviewers.errors import (
            classify_error, RETRYABLE_TYPES,
            MAX_TRANSIENT_RETRIES, RETRY_BACKOFF_SECONDS,
        )

        client = self._get_client()

        for attempt in range(1 + MAX_TRANSIENT_RETRIES):
            try:
                with client.messages.stream(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                ) as stream:
                    resp = stream.get_final_message()
                break
            except Exception as e:
                error_type = classify_error(e)

                if error_type in RETRYABLE_TYPES and attempt < MAX_TRANSIENT_RETRIES:
                    delay = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                    retry_num = attempt + 1
                    print(
                        f"[{self.name}] transient error, retry {retry_num}/{MAX_TRANSIENT_RETRIES} "
                        f"after {delay}s: {e}",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue

                if error_type in RETRYABLE_TYPES:
                    raise RuntimeError(
                        f"Anthropic call failed after {MAX_TRANSIENT_RETRIES} retries ({error_type.value}): {e}"
                    )

                raise RuntimeError(f"Anthropic call failed ({error_type.value}): {e}")

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

        # ---- diagnostic ----
        stop = getattr(resp, "stop_reason", None)
        if stop == "max_tokens":
            print(
                f"[{self.name}] WARNING: response truncated (stop_reason=max_tokens, "
                f"limit={max_tokens}). JSON may be incomplete.",
                file=sys.stderr,
            )
        print(
            f"[{self.name}] raw output: {len(content)} chars, "
            f"{len(content.splitlines())} lines, stop_reason={stop}",
            file=sys.stderr,
        )

        # ---- normalize fenced JSON / stray preamble ----
        s = content.strip()

        if s.startswith("```"):
            lines = s.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines).strip()

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

        # ---- diagnostic: section item counts ----
        _diag_parts = []
        for _dk in ("pillar_claims", "questionable_claims", "omission_candidates",
                     "counterfactual_requirements", "cross_claim_votes",
                     "claim_omissions", "article_omissions", "framing_omissions"):
            _dv = data.get(_dk)
            if isinstance(_dv, list):
                _diag_parts.append(f"{_dk}={len(_dv)}")
        if _diag_parts:
            print(f"[{self.name}] sections: {', '.join(_diag_parts)}", file=sys.stderr)

        return data

    # ----------------------------
    # Public API
    # ----------------------------

    # Keys that enrichment may contribute to the final pack.
    _ENRICHMENT_KEYS = frozenset({
        "scope_markers", "causal_links", "article_patterns",
        "omission_candidates", "counterfactual_requirements",
        "claim_omissions", "article_omissions", "framing_omissions",
        "argument_summary", "object_discipline_check",
        "rival_narratives",
        "argument_integrity",
    })

    def run_triage(self, inp: ReviewerInputs) -> Dict[str, Any]:
        """Pass 1: skeletal triage — core fields only, fast and low-token."""
        gsae_enabled = inp.config.get("gsae_settings", {}).get("enabled") is True
        system_prompt = build_system_prompt("judge", "machine", include_gsae=gsae_enabled)

        print(f"[{self.name}] Pass 1: skeletal triage", file=sys.stderr)
        triage = self._call_json(system_prompt, self._triage_prompt(inp), max_tokens=8192)
        triage["reviewer"] = self.name
        triage["cross_claim_votes"] = []
        triage = self._prefix_claim_ids(triage)
        return triage

    def run_enrichment(self, inp: ReviewerInputs, spine: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 2: structural forensics using cross-reviewer merged spine."""
        gsae_enabled = inp.config.get("gsae_settings", {}).get("enabled") is True
        system_prompt = build_system_prompt("judge", "machine", include_gsae=gsae_enabled)

        print(f"[{self.name}] Pass 2: enrichment", file=sys.stderr)
        enrichment = self._call_json(
            system_prompt, self._enrichment_prompt(inp, spine), max_tokens=8192,
        )
        return enrichment

    def run_phase1(self, inp: ReviewerInputs) -> Dict[str, Any]:
        """Backward-compat wrapper: triage + enrichment in one call."""
        triage = self.run_triage(inp)
        enrichment = self.run_enrichment(inp, triage)

        merged = dict(triage)
        for k, v in enrichment.items():
            if k in self._ENRICHMENT_KEYS:
                merged[k] = v
        return merged

    def run_phase2(self, inp: ReviewerInputs, cross_review_payload: Dict[str, Any]) -> Dict[str, Any]:
        phase1_all = cross_review_payload["phase1_outputs"]
        my_phase1 = phase1_all[self.name]

        gsae_enabled = inp.config.get("gsae_settings", {}).get("enabled") is True
        system_prompt = build_system_prompt("judge", "machine", include_gsae=gsae_enabled)
        phase2_out = self._call_json(system_prompt, self._phase2_prompt(inp, cross_review_payload))
        if not isinstance(phase2_out, dict):
            raise RuntimeError(f"{self.name} Phase2 returned non-dict: {type(phase2_out)}")

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
            "claim_omissions",
            "article_omissions",
            "framing_omissions",
            "argument_summary",
            "object_discipline_check",
            "evidence_density",
        }

        for k, v in phase2_out.items():
            if k in allowed_overrides or k == "reviewer":
                merged[k] = v

        merged["reviewer"] = self.name

        if "cross_claim_votes" not in merged:
            merged["cross_claim_votes"] = my_phase1.get("cross_claim_votes", [])

        merged = self._prefix_claim_ids(merged)
        return merged
