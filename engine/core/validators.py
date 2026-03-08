#!/usr/bin/env python3
"""
FILE: engine/core/validators.py
VERSION: 0.5.0
PURPOSE:
Fail-closed validators for Survivor run_state and reviewer packs.

CONTRACT:
- Fail-closed except for explicit policy clamps that truncate + emit _policy_warnings.
- Key sets are imported from engine.core.schema_constants — do not hardcode them here.

CHANGES IN v0.5.0:
- Layer 7 EID sanitization strips phantom evidence_eids before global integrity check.
- validate_run injects config["_available_eids"] so normalize_reviewer_pack can sanitize phase2 packs.
- PEG-related stabilization cycle completed in tests:
  phantom EID behavior updated from raise -> strip.
- Minor grammar fix in reader_interpretation pluralization ("was/were").

CHANGES IN v0.4.0 (Triage Model — PR2):
- Removed legacy bridge (claims → questionable_claims copy). All packs must now use
  pillar_claims + questionable_claims + background_claims_summary directly.

CHANGES IN v0.3.0 (Triage Model — PR1):
- Replace single claims list with pillar_claims + questionable_claims +
  background_claims_summary (triage architecture).
- _validate_claims() → _validate_claim_list(claims, list_name) — parameterized.
- New: _validate_background_claims_summary() — semi-strict (2 required ints).
- New: _dedupe_claim_category_collision() — E5 trap, dedupe-to-pillar + warning.
- Dual clamps: max_pillar_claims_per_reviewer + max_questionable_claims_per_reviewer.
- Vote cleanup uses kept_ids = union(pillar_ids, questionable_ids).
- validate_run() claim registry uses list_triage_claims().

CHANGES IN v0.2.2:
- whole_article_judgment.evidence_eids emptiness failure is now structured
  (path/expected/got + error_code=missing_whole_article_evidence) so Repair Gate can run.
- Export normalize_reviewer_pack() (public).
- validate_reviewer_pack now calls normalize_reviewer_pack().
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from engine.core.schema_constants import (
    ARTICLE_CLASSIFICATIONS,
    AUTHORITY_SOURCES_EXEMPT_STATUSES,
    CLAIM_TYPES,
    CLASSIFICATION_BUCKET_VALUES,
    CONFIDENCE_VALUES,
    GSAE_ARTIFACT_REQUIRED_KEYS,
    GSAE_SETTINGS_REQUIRED_KEYS,
    GSAE_SUBJECT_REQUIRED_KEYS,
    GSAE_SYMMETRY_PACKET_REQUIRED_KEYS,
    GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS,
    INTEGRITY_SCALE,
    REVIEWER_PACK_OPTIONAL_KEYS,
    REVIEWER_PACK_REQUIRED_KEYS,
    SEVERITY_TIER_VALUES_ORDERED,
    SYMMETRY_BAND_VALUES_ORDERED,
    SYMMETRY_FIELDS_ALL,
    SYMMETRY_STATUS_VALUES,
    EMPTY_EIDS_ALLOWED_CLASSIFICATIONS,
    UNCERTAIN_CLASSIFICATIONS,
    VOTE_VALUES,
)
from engine.core.errors import ReviewerPackValidationError
from engine.core.triage_utils import list_triage_claims


def _require(
    cond: bool,
    msg: str,
    *,
    path: str | None = None,
    expected: str | None = None,
    got: str | None = None,
    error_code: str | None = None,
) -> None:
    if cond:
        return
    if path is None:
        raise RuntimeError(msg)
    err: Dict[str, str] = {
        "path": path,
        "expected": expected or "(see schema)",
        "got": got or "(unknown)",
        "message": msg,
    }
    if error_code is not None:
        err["error_code"] = error_code
    raise ReviewerPackValidationError([err])


def _is_list_of_str(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


# ---------------------------------------------------------------------------
# whole_article_judgment validation
# ---------------------------------------------------------------------------


def _validate_whole_article_judgment(pack: Dict[str, Any]) -> None:
    waj = pack.get("whole_article_judgment")
    _require(isinstance(waj, dict), "ReviewerPack missing whole_article_judgment dict")

    classification = waj.get("classification")
    confidence = waj.get("confidence")
    eids = waj.get("evidence_eids")

    _require(isinstance(classification, str), "whole_article_judgment.classification must be str")
    _require(
        classification in ARTICLE_CLASSIFICATIONS,
        f"whole_article_judgment.classification invalid: {classification!r}",
        path="whole_article_judgment.classification",
        expected=" | ".join(sorted(ARTICLE_CLASSIFICATIONS)),
        got=repr(classification),
    )
    _require(
        confidence in CONFIDENCE_VALUES,
        f"whole_article_judgment.confidence invalid: {confidence!r}",
        path="whole_article_judgment.confidence",
        expected=" | ".join(sorted(CONFIDENCE_VALUES)),
        got=repr(confidence),
    )
    _require(_is_list_of_str(eids), "whole_article_judgment.evidence_eids must be list[str]")

    # (B) Uncertain classification: require uncertainty_basis + check_scope.
    if classification in UNCERTAIN_CLASSIFICATIONS:
        uncertainty_basis = waj.get("uncertainty_basis")
        _require(
            isinstance(uncertainty_basis, str) and uncertainty_basis.strip(),
            "whole_article_judgment.uncertainty_basis must be non-empty str when classification is uncertain",
        )
        check_scope = waj.get("check_scope") or waj.get("search_scope")
        _require(
            isinstance(check_scope, str) and check_scope.strip(),
            "whole_article_judgment.check_scope (or search_scope) must be non-empty str when classification is uncertain",
        )
        return

    # (B2) Some classifications allow empty evidence_eids at whole-article level.
    if classification not in EMPTY_EIDS_ALLOWED_CLASSIFICATIONS:
        _require(
            len(eids) > 0,
            "whole_article_judgment.evidence_eids must be non-empty unless classification is uncertain or reporting",
            path="whole_article_judgment.evidence_eids",
            expected="non-empty list[str] of EvidenceBank EIDs (unless classification is uncertain/reporting)",
            got=repr(eids),
            error_code="missing_whole_article_evidence",
        )

    # (C) Integrity Scale — validate if the field is present in waj.
    integrity_rating = waj.get("integrity_rating")
    if integrity_rating is not None:
        _require(
            integrity_rating in INTEGRITY_SCALE,
            f"whole_article_judgment.integrity_rating invalid: {integrity_rating!r}",
        )


# ---------------------------------------------------------------------------
# Claims validation (parameterized for pillar / questionable)
# ---------------------------------------------------------------------------


def _validate_claim_list(claims: List[Any], list_name: str) -> None:
    """Validate a list of Claim dicts. list_name is for error messages."""
    for i, claim in enumerate(claims):
        _require(isinstance(claim, dict), f"{list_name}[{i}] must be dict")
        _require(
            isinstance(claim.get("claim_id"), str) and claim["claim_id"].strip(),
            f"{list_name}[{i}].claim_id must be non-empty str",
        )
        _require(
            isinstance(claim.get("text"), str) and claim["text"].strip(),
            f"{list_name}[{i}].text must be non-empty str",
        )
        _require(
            claim.get("type") in CLAIM_TYPES,
            f"{list_name}[{i}].type invalid: {claim.get('type')!r}",
            path=f"{list_name}[{i}].type",
            expected=" | ".join(sorted(CLAIM_TYPES)),
            got=repr(claim.get("type")),
        )
        _require(
            _is_list_of_str(claim.get("evidence_eids")),
            f"{list_name}[{i}].evidence_eids must be list[str]",
        )
        centrality = claim.get("centrality")
        _require(
            isinstance(centrality, int) and centrality in (1, 2, 3),
            f"{list_name}[{i}].centrality must be 1, 2, or 3",
        )


# ---------------------------------------------------------------------------
# background_claims_summary validation (semi-strict: 2 required ints)
# ---------------------------------------------------------------------------


def _validate_background_claims_summary(pack: Dict[str, Any]) -> None:
    bcs = pack.get("background_claims_summary")
    _require(isinstance(bcs, dict), "background_claims_summary must be dict")

    tce = bcs.get("total_claims_estimate")
    ntc = bcs.get("not_triaged_count")

    _require(
        isinstance(tce, int) and tce >= 0,
        "background_claims_summary.total_claims_estimate must be int >= 0",
    )
    _require(
        isinstance(ntc, int) and ntc >= 0,
        "background_claims_summary.not_triaged_count must be int >= 0",
    )

    samples = bcs.get("samples")
    if samples is not None:
        _require(
            _is_list_of_str(samples),
            "background_claims_summary.samples must be list[str] when present",
        )


# ---------------------------------------------------------------------------
# E5: Category collision trap (dedupe-to-pillar + warning)
# ---------------------------------------------------------------------------


def _dedupe_claim_category_collision(pack: Dict[str, Any]) -> None:
    """If a claim_id appears in both pillar_claims and questionable_claims,
    keep it in pillar_claims and remove from questionable_claims.
    Emits _policy_warnings entry."""
    pillar = pack.get("pillar_claims")
    questionable = pack.get("questionable_claims")
    if not isinstance(pillar, list) or not isinstance(questionable, list):
        return

    pillar_ids: Set[str] = set()
    for c in pillar:
        if isinstance(c, dict):
            cid = c.get("claim_id")
            if isinstance(cid, str) and cid.strip():
                pillar_ids.add(cid)

    if not pillar_ids:
        return

    new_q: List[Any] = []
    collisions: List[str] = []
    for c in questionable:
        if not isinstance(c, dict):
            continue
        cid = c.get("claim_id")
        if isinstance(cid, str) and cid.strip() and cid in pillar_ids:
            collisions.append(cid)
            continue
        new_q.append(c)

    if collisions:
        pack["questionable_claims"] = new_q
        warnings = pack.setdefault("_policy_warnings", [])
        warnings.append({
            "code": "claim_category_collision_deduped",
            "collision_count": len(collisions),
            "collision_ids_sample": collisions[:10],
            "message": (
                "Same claim_id appeared in both pillar_claims and questionable_claims; "
                "kept in pillar_claims and removed from questionable_claims."
            ),
        })


# ---------------------------------------------------------------------------
# Cross-claim votes validation
# ---------------------------------------------------------------------------


def _validate_cross_claim_votes(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    cap = int(config["max_near_duplicate_links"])
    votes = pack.get("cross_claim_votes", [])
    _require(isinstance(votes, list), "ReviewerPack.cross_claim_votes must be list")

    for i, v in enumerate(votes):
        _require(isinstance(v, dict), f"cross_claim_votes[{i}] must be dict")

        # (v0.2.1) claim_id must be non-empty str
        cid = v.get("claim_id")
        _require(
            isinstance(cid, str) and cid.strip(),
            f"cross_claim_votes[{i}].claim_id must be non-empty str",
        )

        vote_val = v.get("vote")
        if vote_val is not None:
            _require(
                vote_val in VOTE_VALUES,
                f"cross_claim_votes[{i}].vote invalid: {vote_val!r}",
                path=f"cross_claim_votes[{i}].vote",
                expected=" | ".join(sorted(VOTE_VALUES)),
                got=repr(vote_val),
            )

        conf_val = v.get("confidence")
        if conf_val is not None:
            _require(
                conf_val in CONFIDENCE_VALUES,
                f"cross_claim_votes[{i}].confidence invalid: {conf_val!r}",
                path=f"cross_claim_votes[{i}].confidence",
                expected=" | ".join(sorted(CONFIDENCE_VALUES)),
                got=repr(conf_val),
            )

        nd = v.get("near_duplicate_of")
        if nd is None:
            continue
        _require(_is_list_of_str(nd), f"cross_claim_votes[{i}].near_duplicate_of must be list[str]")
        _require(len(nd) <= cap, f"cross_claim_votes[{i}].near_duplicate_of exceeds cap {cap}")


# ---------------------------------------------------------------------------
# normalize + validate_reviewer_pack
# ---------------------------------------------------------------------------


def normalize_reviewer_pack(
    pack: Dict[str, Any],
    available_eids: Optional[Set[str]] = None,
) -> None:
    """Semantic normalizer — drift firewall for LLM enum outputs.

    Layers 1-6: synonym mapping, centrality clamping, GSAE normalization.
    Layer 7: EID sanitization — strips evidence_eids not in available_eids.

    Idempotent: safe to call multiple times on the same pack.
    Called by the translator BEFORE lossless translation so that synonym
    drift (e.g. "assertion" -> "factual") never wastes a repair attempt.
    Also called inside validate_reviewer_pack() as a belt-and-suspenders
    safety net.
    """
    # --- Default missing low-value required keys (LLMs drop under token pressure) ---
    _REQUIRED_DEFAULTS = {
        "claim_tickets": [],
        "article_tickets": [],
        "evidence_density": {"claims_count": 0, "claims_with_internal_support": 0, "external_sources_count": 0},
        "scope_markers": [],
        "causal_links": [],
        "article_patterns": [],
        "omission_candidates": [],
        "counterfactual_requirements": [],
        "cross_claim_votes": [],
    }
    for k, default in _REQUIRED_DEFAULTS.items():
        if k not in pack:
            pack[k] = default

    # --- Classification synonyms ---
    waj = pack.get("whole_article_judgment")
    if isinstance(waj, dict):
        raw = waj.get("classification")
        if isinstance(raw, str):
            key = raw.strip().lower()
            _CLASSIFICATION_MAP = {
                "news": "reporting",
                "straight_news": "reporting",
                "news_reporting": "reporting",
                "factual_reporting": "reporting",
                "commentary": "analysis",
                "opinion": "analysis",
                "editorial": "analysis",
                "propaganda": "propaganda-patterned advocacy",
                "propaganda_patterned": "propaganda-patterned advocacy",
                "propaganda_patterned_advocacy": "propaganda-patterned advocacy",
            }
            if key in _CLASSIFICATION_MAP:
                waj["classification"] = _CLASSIFICATION_MAP[key]

    # --- Claim type synonyms ---
    _CLAIM_TYPE_MAP = {
        "stated_position": "normative",
        "stance": "normative",
        "opinion": "normative",
        "argument": "normative",
        "observation": "factual",
        "reporting": "factual",
        "report": "factual",
        "fact": "factual",
        "assertion": "factual",  # OpenAI commonly outputs "assertion"
        "statement": "factual",
        "forecast": "predictive",
        "prediction": "predictive",
        "projection": "predictive",
        "explanation": "causal",
        "cause": "causal",
        "result": "causal",
        # compound types LLMs invent
        "prediction_or_opinion": "predictive",
        "factual_claim": "factual",
        "causal_claim": "causal",
        "normative_claim": "normative",
        "predictive_claim": "predictive",
        # creative types Claude/Gemini invent under token pressure
        "historical_generalization": "factual",
        "conceptual_claim": "normative",
        "historical_causal_claim": "causal",
        "analytical_claim": "normative",
        "unsupported_generalization": "factual",
        "question_begging_claim": "normative",
        "scope_softening_concession": "normative",
        "interpretive": "normative",
        "empirical": "factual",
        "evaluative": "normative",
        "comparative": "factual",
        "definitional": "factual",
    }

    # --- Centrality clamping (must be 1, 2, or 3) + claim type normalization ---
    _claim_lists_to_normalize = []
    for key in ("pillar_claims", "questionable_claims"):
        cl = pack.get(key)
        if isinstance(cl, list):
            _claim_lists_to_normalize.append(cl)

    for claims in _claim_lists_to_normalize:
        for c in claims:
            if not isinstance(c, dict):
                continue
            raw_c = c.get("centrality")
            try:
                v = int(raw_c)
            except (TypeError, ValueError):
                v = 2  # default to mid-range
            c["centrality"] = max(1, min(3, v))

            raw_type = c.get("type")
            if isinstance(raw_type, str):
                key = raw_type.strip().lower().replace(" ", "_")
                if key in _CLAIM_TYPE_MAP:
                    c["type"] = _CLAIM_TYPE_MAP[key]
                elif key not in CLAIM_TYPES:
                    # Unknown type — default to factual rather than fail
                    c["type"] = "factual"

    # --- GSAE classification_bucket normalization ---
    obs = pack.get("gsae_observation")
    if isinstance(obs, dict):
        raw_bucket = obs.get("classification_bucket")
        if isinstance(raw_bucket, str):
            bkey = raw_bucket.strip().lower().replace(" ", "_").replace("-", "_")
            _GSAE_BUCKET_MAP = {
                "propaganda_patterned_advocacy": "mobilizing",
                "propaganda": "mobilizing",
                "advocacy": "mobilizing",
                "propaganda_patterned": "mobilizing",
                "analysis": "interpretive",
                "commentary": "interpretive",
                "opinion": "normative",
                "editorial": "normative",
                "news": "reporting",
                "news_reporting": "reporting",
                "factual_reporting": "reporting",
                "mixed": "ambiguous",
                "uncertain": "ambiguous",
            }
            if bkey in _GSAE_BUCKET_MAP:
                obs["classification_bucket"] = _GSAE_BUCKET_MAP[bkey]
            elif bkey not in CLASSIFICATION_BUCKET_VALUES:
                obs["classification_bucket"] = "ambiguous"

        # --- GSAE severity tier normalization ---
        _SEVERITY_MAP = {
            "low": "minimal",
            "none": "minimal",
            "minor": "minimal",
            "medium": "moderate",
            "mid": "moderate",
            "severe": "critical",
            "very_high": "critical",
            "extreme": "critical",
        }
        _SEVERITY_LEGAL = set(SEVERITY_TIER_VALUES_ORDERED)
        for sfield in ("severity_tier", "severity_toward_subject", "severity_toward_counterparty"):
            raw_sev = obs.get(sfield)
            if isinstance(raw_sev, str):
                skey = raw_sev.strip().lower().replace(" ", "_")
                if skey in _SEVERITY_MAP:
                    obs[sfield] = _SEVERITY_MAP[skey]
                elif skey not in _SEVERITY_LEGAL:
                    obs[sfield] = "moderate"

        # --- GSAE confidence_band normalization ---
        _BAND_MAP = {
            "low": "sb_low",
            "medium": "sb_mid",
            "mid": "sb_mid",
            "high": "sb_high",
            "max": "sb_max",
            "maximum": "sb_max",
        }
        _BAND_LEGAL = set(SYMMETRY_BAND_VALUES_ORDERED)
        raw_band = obs.get("confidence_band")
        if isinstance(raw_band, str):
            band_key = raw_band.strip().lower().replace(" ", "_")
            if band_key in _BAND_MAP:
                obs["confidence_band"] = _BAND_MAP[band_key]
            elif band_key not in _BAND_LEGAL:
                obs["confidence_band"] = "sb_mid"

    # --- argument_integrity claim-ID repair ---
    # LLMs sometimes hallucinate claim IDs from other reviewers' namespaces
    # (e.g. Gemini emitting "claude-PC3"). Filter to only IDs that exist in
    # this reviewer's own pillar_claims + questionable_claims.
    ai = pack.get("argument_integrity")
    if isinstance(ai, dict):
        own_ids: Set[str] = set()
        for key in ("pillar_claims", "questionable_claims"):
            cl = pack.get(key)
            if isinstance(cl, list):
                for c in cl:
                    if isinstance(c, dict):
                        cid = c.get("claim_id")
                        if isinstance(cid, str) and cid.strip():
                            own_ids.add(cid)

        for id_key in ("load_bearing_claim_ids", "weak_link_claim_ids"):
            raw_ids = ai.get(id_key)
            if isinstance(raw_ids, list):
                cleaned = [cid for cid in raw_ids if cid in own_ids]
                dropped = len(raw_ids) - len(cleaned)
                if dropped > 0:
                    ai[id_key] = cleaned
                    warnings = pack.setdefault("_policy_warnings", [])
                    warnings.append({
                        "code": "foreign_claim_id_in_argument_integrity",
                        "field": f"argument_integrity.{id_key}",
                        "dropped_count": dropped,
                        "kept_count": len(cleaned),
                        "message": (
                            f"Dropped {dropped} claim ID(s) from {id_key} "
                            f"not found in this reviewer's own claims."
                        ),
                    })

    # --- Layer 8: object_discipline_check repair ---
    odc = pack.get("object_discipline_check")
    if isinstance(odc, dict):
        if odc.get("status") not in ("pass", "fail"):
            odc["status"] = "pass"
        reason = odc.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            odc["reason"] = "No reason provided by reviewer."

    # --- Layer 7: Evidence EID sanitization ---
    if available_eids is not None:
        def _filter_eids(lst):
            if not isinstance(lst, list):
                return lst
            return [eid for eid in lst if isinstance(eid, str) and eid in available_eids]

        # whole_article_judgment
        waj = pack.get("whole_article_judgment")
        if isinstance(waj, dict):
            waj["evidence_eids"] = _filter_eids(waj.get("evidence_eids"))

        # claims
        for key in ("pillar_claims", "questionable_claims"):
            claims = pack.get(key)
            if isinstance(claims, list):
                for c in claims:
                    if isinstance(c, dict):
                        c["evidence_eids"] = _filter_eids(c.get("evidence_eids"))


def _clamp_claim_list(
    pack: Dict[str, Any],
    list_key: str,
    max_count: int,
    warning_code: str,
) -> List[Any]:
    """Truncate a claim list to max_count, emit _policy_warnings. Returns kept list."""
    claims = pack.get(list_key)
    _require(isinstance(claims, list), f"ReviewerPack.{list_key} must be list")
    if len(claims) > max_count:
        returned_count = len(claims)
        pack[list_key] = claims[:max_count]
        warnings = pack.setdefault("_policy_warnings", [])
        warnings.append({
            "code": warning_code,
            "returned_count": returned_count,
            "kept_count": max_count,
            "dropped_count": returned_count - max_count,
            "message": (
                f"Reviewer returned {returned_count} {list_key}, exceeding "
                f"cap={max_count}. Truncated to first {max_count}."
            ),
        })
    return pack[list_key]


def validate_reviewer_pack(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require(isinstance(pack, dict), "ReviewerPack must be dict")
    raw_available_eids = config.get("_available_eids")
    available_eids = raw_available_eids if isinstance(raw_available_eids, set) else None
    normalize_reviewer_pack(pack, available_eids)
    _dedupe_claim_category_collision(pack)

    # (v0.2.1) reviewer must be a non-empty str
    reviewer = pack.get("reviewer")
    _require(isinstance(reviewer, str) and reviewer.strip(), "ReviewerPack.reviewer missing/invalid")

    # (A) Key sets from schema_constants — no hardcoding here.
    actual_keys = set(pack.keys())
    allowed_keys = REVIEWER_PACK_REQUIRED_KEYS | REVIEWER_PACK_OPTIONAL_KEYS | {"reviewer"}

    missing = sorted(REVIEWER_PACK_REQUIRED_KEYS - actual_keys)
    _require(not missing, f"ReviewerPack missing required key(s): {missing}")

    extra = sorted(actual_keys - allowed_keys)
    _require(not extra, f"ReviewerPack has unknown extra key(s): {extra}")

    # Optional Tier C blocks (validated strictly if present).
    if "gsae_observation" in pack:
        _validate_gsae_symmetry_packet(pack["gsae_observation"])
    if "gsae_subject" in pack:
        _validate_gsae_subject(pack["gsae_subject"])

    _validate_whole_article_judgment(pack)

    # Validate + clamp both triage claim lists
    pillar = pack.get("pillar_claims", [])
    questionable = pack.get("questionable_claims", [])
    _validate_claim_list(pillar, "pillar_claims")
    _validate_claim_list(questionable, "questionable_claims")
    _validate_background_claims_summary(pack)

    max_pillar = int(config.get("max_pillar_claims_per_reviewer", 15))
    max_questionable = int(config.get("max_questionable_claims_per_reviewer", 30))

    pillar = _clamp_claim_list(pack, "pillar_claims", max_pillar, "pillar_claims_truncated")
    questionable = _clamp_claim_list(pack, "questionable_claims", max_questionable, "questionable_claims_truncated")

    # Clamp omission_candidates and counterfactual_requirements
    max_omit = int(config.get("max_omission_candidates", 5))
    max_cf = int(config.get("max_counterfactuals", 5))
    for list_key, cap, warn_code in (
        ("omission_candidates", max_omit, "omission_candidates_truncated"),
        ("counterfactual_requirements", max_cf, "counterfactuals_truncated"),
    ):
        items = pack.get(list_key)
        if isinstance(items, list) and len(items) > cap:
            pack[list_key] = items[:cap]
            warnings = pack.setdefault("_policy_warnings", [])
            warnings.append({
                "code": warn_code,
                "message": f"{list_key} truncated from {len(items)} to {cap}",
            })

    # Vote cleanup: kept_ids = union(pillar_ids, questionable_ids)
    kept_ids: Set[str] = set()
    for c in pillar:
        if isinstance(c, dict):
            cid = c.get("claim_id")
            if isinstance(cid, str) and cid.strip():
                kept_ids.add(cid)
    for c in questionable:
        if isinstance(c, dict):
            cid = c.get("claim_id")
            if isinstance(cid, str) and cid.strip():
                kept_ids.add(cid)

    votes = pack.get("cross_claim_votes")
    if isinstance(votes, list):
        filtered = []
        for v in votes:
            if not isinstance(v, dict):
                continue
            if v.get("claim_id") not in kept_ids:
                continue
            nd = v.get("near_duplicate_of")
            if isinstance(nd, list):
                v = dict(v)
                v["near_duplicate_of"] = [x for x in nd if isinstance(x, str) and x in kept_ids]
            filtered.append(v)
        pack["cross_claim_votes"] = filtered

    _validate_cross_claim_votes(pack, config)

    # Structural forensics fields (optional — validated strictly if present)
    if "claim_omissions" in pack:
        _validate_claim_omissions(pack, kept_ids)
    if "article_omissions" in pack:
        _validate_article_omissions(pack, kept_ids)
    if "framing_omissions" in pack:
        _validate_framing_omissions(pack)
    if "argument_summary" in pack:
        _validate_argument_summary(pack)
    if "object_discipline_check" in pack:
        _validate_object_discipline_check(pack)
    if "rival_narratives" in pack:
        _validate_rival_narratives(pack)
    if "argument_integrity" in pack:
        _validate_argument_integrity(pack)


# ---------------------------------------------------------------------------
# Structural forensics validators (v0.5)
# ---------------------------------------------------------------------------


def _validate_claim_omissions(pack: Dict[str, Any], kept_ids: Set[str]) -> None:
    items = pack["claim_omissions"]
    _require(isinstance(items, list), "claim_omissions must be list")
    for i, item in enumerate(items):
        _require(isinstance(item, dict), f"claim_omissions[{i}] must be dict")
        tid = item.get("target_claim_id")
        _require(
            isinstance(tid, str) and tid.strip(),
            f"claim_omissions[{i}].target_claim_id must be non-empty str",
        )
        mf = item.get("missing_frame")
        _require(
            isinstance(mf, str) and mf.strip(),
            f"claim_omissions[{i}].missing_frame must be non-empty str",
        )
        conf = item.get("confidence")
        _require(
            conf in CONFIDENCE_VALUES,
            f"claim_omissions[{i}].confidence must be one of {sorted(CONFIDENCE_VALUES)}",
        )


def _validate_article_omissions(pack: Dict[str, Any], kept_ids: Set[str]) -> None:
    items = pack["article_omissions"]
    _require(isinstance(items, list), "article_omissions must be list")
    for i, item in enumerate(items):
        _require(isinstance(item, dict), f"article_omissions[{i}] must be dict")
        mf = item.get("missing_frame")
        _require(
            isinstance(mf, str) and mf.strip(),
            f"article_omissions[{i}].missing_frame must be non-empty str",
        )
        aids = item.get("affected_claim_ids")
        _require(
            isinstance(aids, list),
            f"article_omissions[{i}].affected_claim_ids must be list",
        )
        conf = item.get("confidence")
        _require(
            conf in CONFIDENCE_VALUES,
            f"article_omissions[{i}].confidence must be one of {sorted(CONFIDENCE_VALUES)}",
        )


def _validate_framing_omissions(pack: Dict[str, Any]) -> None:
    items = pack["framing_omissions"]
    _require(isinstance(items, list), "framing_omissions must be list")
    for i, item in enumerate(items):
        _require(isinstance(item, dict), f"framing_omissions[{i}] must be dict")
        fua = item.get("frame_used_by_article")
        _require(
            isinstance(fua, str) and fua.strip(),
            f"framing_omissions[{i}].frame_used_by_article must be non-empty str",
        )
        mf = item.get("missing_frame")
        _require(
            isinstance(mf, str) and mf.strip(),
            f"framing_omissions[{i}].missing_frame must be non-empty str",
        )
        af = item.get("alternative_frames")
        _require(
            isinstance(af, list) and all(isinstance(f, str) for f in af),
            f"framing_omissions[{i}].alternative_frames must be list[str]",
        )
        conf = item.get("confidence")
        _require(
            conf in CONFIDENCE_VALUES,
            f"framing_omissions[{i}].confidence must be one of {sorted(CONFIDENCE_VALUES)}",
        )


def _validate_argument_summary(pack: Dict[str, Any]) -> None:
    summary = pack["argument_summary"]
    _require(isinstance(summary, dict), "argument_summary must be dict")
    mc = summary.get("main_conclusion")
    _require(
        isinstance(mc, str) and mc.strip(),
        "argument_summary.main_conclusion must be non-empty str",
    )
    sr = summary.get("supporting_reasons")
    _require(
        isinstance(sr, list) and all(isinstance(s, str) for s in sr),
        "argument_summary.supporting_reasons must be list[str]",
    )
    kr = summary.get("key_rival_explanations_missing")
    _require(
        isinstance(kr, list) and all(isinstance(s, str) for s in kr),
        "argument_summary.key_rival_explanations_missing must be list[str]",
    )


_FRAGILITY_VALUES: frozenset[str] = frozenset({"low", "elevated", "high"})


def _validate_rival_narratives(pack: Dict[str, Any]) -> None:
    items = pack["rival_narratives"]
    _require(isinstance(items, list), "rival_narratives must be list")
    for i, item in enumerate(items):
        _require(isinstance(item, dict), f"rival_narratives[{i}] must be dict")
        rnid = item.get("rival_narrative_id")
        _require(
            isinstance(rnid, str) and rnid.strip(),
            f"rival_narratives[{i}].rival_narrative_id must be non-empty str",
        )
        lens = item.get("lens")
        _require(
            isinstance(lens, str) and lens.strip(),
            f"rival_narratives[{i}].lens must be non-empty str",
        )
        summary = item.get("summary")
        _require(
            isinstance(summary, str) and summary.strip(),
            f"rival_narratives[{i}].summary must be non-empty str",
        )
        scfu = item.get("same_core_facts_used")
        _require(
            isinstance(scfu, list),
            f"rival_narratives[{i}].same_core_facts_used must be list",
        )
        cwit = item.get("claims_weakened_if_true")
        _require(
            isinstance(cwit, list),
            f"rival_narratives[{i}].claims_weakened_if_true must be list",
        )
        sf = item.get("structural_fragility")
        _require(
            sf in _FRAGILITY_VALUES,
            f"rival_narratives[{i}].structural_fragility must be one of {sorted(_FRAGILITY_VALUES)}",
        )
        conf = item.get("confidence")
        _require(
            conf in CONFIDENCE_VALUES,
            f"rival_narratives[{i}].confidence must be one of {sorted(CONFIDENCE_VALUES)}",
        )


def _validate_argument_integrity(pack: Dict[str, Any]) -> None:
    obj = pack["argument_integrity"]
    _require(isinstance(obj, dict), "argument_integrity must be dict")

    main_conclusion = obj.get("main_conclusion")
    _require(
        isinstance(main_conclusion, str) and main_conclusion.strip(),
        "argument_integrity.main_conclusion must be non-empty str",
    )

    # Collect valid claim_ids from the pack
    valid_ids: Set[str] = set()
    for key in ("pillar_claims", "questionable_claims"):
        claims = pack.get(key, [])
        if isinstance(claims, list):
            for c in claims:
                if isinstance(c, dict):
                    cid = c.get("claim_id")
                    if isinstance(cid, str) and cid.strip():
                        valid_ids.add(cid)

    load_bearing = obj.get("load_bearing_claim_ids")
    _require(
        _is_list_of_str(load_bearing),
        "argument_integrity.load_bearing_claim_ids must be list[str]",
    )
    for cid in load_bearing:
        _require(
            cid in valid_ids,
            f"argument_integrity.load_bearing_claim_ids contains unknown claim_id: {cid!r}",
        )

    weak_links = obj.get("weak_link_claim_ids")
    _require(
        _is_list_of_str(weak_links),
        "argument_integrity.weak_link_claim_ids must be list[str]",
    )
    for cid in weak_links:
        _require(
            cid in valid_ids,
            f"argument_integrity.weak_link_claim_ids contains unknown claim_id: {cid!r}",
        )

    chain = obj.get("support_chain_summary")
    _require(
        _is_list_of_str(chain),
        "argument_integrity.support_chain_summary must be list[str]",
    )

    fragility = obj.get("argument_fragility")
    _require(
        fragility in _FRAGILITY_VALUES,
        f"argument_integrity.argument_fragility must be one of {sorted(_FRAGILITY_VALUES)}",
    )

    reason = obj.get("reason")
    _require(
        isinstance(reason, str) and reason.strip(),
        "argument_integrity.reason must be non-empty str",
    )


def _validate_object_discipline_check(pack: Dict[str, Any]) -> None:
    odc = pack["object_discipline_check"]
    _require(isinstance(odc, dict), "object_discipline_check must be dict")
    status = odc.get("status")
    _require(
        status in ("pass", "fail"),
        "object_discipline_check.status must be 'pass' or 'fail'",
    )
    reason = odc.get("reason")
    _require(
        isinstance(reason, str) and reason.strip(),
        "object_discipline_check.reason must be non-empty str",
    )


# ---------------------------------------------------------------------------
# EID collection (iterative, cap-guarded — v0.2.1)
# ---------------------------------------------------------------------------


def _collect_eids(obj: Any, out: List[str], *, max_nodes: int = 200_000) -> None:
    stack = [obj]
    seen = 0
    while stack:
        seen += 1
        if seen > max_nodes:
            raise RuntimeError(
                f"EID collection exceeded max_nodes={max_nodes} (possible nested/hostile structure)"
            )
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == "evidence_eids" and isinstance(v, list):
                    for eid in v:
                        if isinstance(eid, str):
                            out.append(eid)
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)


def _strip_bad_eids(obj: Any, valid_eids: Set[str]) -> None:
    """In-place strip of evidence_eids not in valid_eids from any nested dict.

    Safety net for the adjudicated dict, which is built from phase2 data
    before validate_run() has a chance to sanitize it.
    """
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == "evidence_eids" and isinstance(v, list):
                    cur[k] = [eid for eid in v if isinstance(eid, str) and eid in valid_eids]
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)


# ---------------------------------------------------------------------------
# (D) EvidenceBank canonical schema validation
# ---------------------------------------------------------------------------


def _validate_evidence_bank_items(
    items: List[Any],
    normalized_text: str | None,
) -> None:
    seen_eids: Set[str] = set()
    seen_quotes: Set[str] = set()

    for i, item in enumerate(items):
        _require(isinstance(item, dict), f"evidence_bank.items[{i}] must be dict")

        eid = item.get("eid")
        _require(
            isinstance(eid, str) and eid.strip(),
            f"evidence_bank.items[{i}].eid must be non-empty str",
        )
        _require(eid not in seen_eids, f"evidence_bank: duplicate eid: {eid!r}")
        seen_eids.add(eid)

        quote = item.get("quote")
        _require(
            isinstance(quote, str) and quote.strip(),
            f"evidence_bank.items[{i}] ({eid}): quote must be non-empty str",
        )
        _require(quote not in seen_quotes, f"evidence_bank: duplicate quote at {eid!r}")
        seen_quotes.add(quote)

        locator = item.get("locator")
        _require(
            isinstance(locator, dict),
            f"evidence_bank.items[{i}] ({eid}): locator must be dict",
        )
        cs = locator.get("char_start")
        ce = locator.get("char_end")
        _require(isinstance(cs, int), f"evidence_bank.items[{i}] ({eid}): locator.char_start must be int")
        _require(isinstance(ce, int), f"evidence_bank.items[{i}] ({eid}): locator.char_end must be int")
        _require(cs >= 0, f"evidence_bank.items[{i}] ({eid}): locator.char_start must be >= 0")
        _require(cs < ce, f"evidence_bank.items[{i}] ({eid}): locator.char_start must be < char_end")

        source_id = item.get("source_id")
        _require(
            isinstance(source_id, str) and source_id.strip(),
            f"evidence_bank.items[{i}] ({eid}): source_id must be non-empty str",
        )

        # Transitional alias enforcement
        text_alias = item.get("text")
        if text_alias is not None:
            _require(
                text_alias == quote,
                f"evidence_bank.items[{i}] ({eid}): text alias must equal quote",
            )

        char_len = item.get("char_len")
        if char_len is not None:
            _require(
                isinstance(char_len, int) and char_len == len(quote),
                f"evidence_bank.items[{i}] ({eid}): char_len must equal len(quote)",
            )

        # Locator length consistency (reconstructibility without source text)
        _require(
            ce - cs == len(quote),
            f"evidence_bank.items[{i}] ({eid}): locator span [{cs}:{ce}] length {ce - cs} "
            f"!= len(quote) {len(quote)}",
        )

        # Full reconstructibility when normalized_text is available
        if normalized_text is not None:
            # (v0.2.1) bounds checks before slicing
            _require(
                cs <= len(normalized_text),
                f"evidence_bank.items[{i}] ({eid}): locator.char_start out of bounds: "
                f"{cs} > len(normalized_text) {len(normalized_text)}",
            )
            _require(
                ce <= len(normalized_text),
                f"evidence_bank.items[{i}] ({eid}): locator.char_end out of bounds: "
                f"{ce} > len(normalized_text) {len(normalized_text)}",
            )
            sliced = normalized_text[cs:ce]
            _require(
                sliced == quote,
                f"evidence_bank.items[{i}] ({eid}): locator mismatch — "
                f"normalized_text[{cs}:{ce}]={sliced!r} != quote={quote!r}",
            )


# ---------------------------------------------------------------------------
# (E) Near-duplicate link-rot validation
# ---------------------------------------------------------------------------


def _validate_near_duplicate_refs(
    phase2: Dict[str, Any],
    claim_registry: Set[str],
) -> None:
    """
    For every near_duplicate_of reference across all reviewer packs,
    ensure the referenced claim_id exists in the claim_registry.
    Raises RuntimeError on any dangling reference.
    """
    for reviewer, pack in phase2.items():
        if not isinstance(pack, dict):
            continue
        votes = pack.get("cross_claim_votes", [])
        if not isinstance(votes, list):
            continue
        for i, v in enumerate(votes):
            if not isinstance(v, dict):
                continue
            nd = v.get("near_duplicate_of")
            if not nd:
                continue
            for ref in nd:
                _require(
                    ref in claim_registry,
                    f"near_duplicate_of dangling reference in {reviewer}.cross_claim_votes[{i}]: "
                    f"{ref!r} not found in claim registry",
                )


# ---------------------------------------------------------------------------
# GSAE — Tier C validation (fail-closed, Tier A integrity)
# ---------------------------------------------------------------------------


def _is_numeric_not_bool(x: Any) -> bool:
    """True if x is int or float but not bool."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _validate_gsae_symmetry_packet(packet: Dict[str, Any]) -> None:
    """Validate a GSAESymmetryPacket dict — strict keyset, vocab, types.

    Accepts exactly one of two keysets:
      v0.2 (legacy): GSAE_SYMMETRY_PACKET_REQUIRED_KEYS (uses severity_tier)
      v0.3 (directional): GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS
            (uses severity_toward_subject + severity_toward_counterparty)
    """
    pfx = "_validate_gsae_symmetry_packet"
    _require(isinstance(packet, dict), f"{pfx}: packet must be dict")

    keys = set(packet.keys())
    schema_keys = {k for k in keys if not k.startswith("raw_")}
    is_v02 = schema_keys == GSAE_SYMMETRY_PACKET_REQUIRED_KEYS
    is_v03 = schema_keys == GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS
    _require(
        is_v02 or is_v03,
        f"{pfx}: key mismatch — keys do not match v0.2 or v0.3 keyset. "
        f"got={sorted(schema_keys)}",
    )

    cb = packet["classification_bucket"]
    _require(
        cb in CLASSIFICATION_BUCKET_VALUES,
        f"{pfx}: classification_bucket invalid: {cb!r}",
        path="gsae_observation.classification_bucket",
        expected=" | ".join(sorted(CLASSIFICATION_BUCKET_VALUES)),
        got=repr(cb),
    )

    il = packet["intent_level"]
    _require(
        isinstance(il, str) and il.strip(),
        f"{pfx}: intent_level must be non-empty str",
    )

    band = packet["confidence_band"]
    _require(
        band in SYMMETRY_BAND_VALUES_ORDERED,
        f"{pfx}: confidence_band invalid: {band!r}",
        path="gsae_observation.confidence_band",
        expected=" | ".join(SYMMETRY_BAND_VALUES_ORDERED),
        got=repr(band),
    )

    rc = packet["requires_corrob"]
    _require(
        isinstance(rc, bool),
        f"{pfx}: requires_corrob must be bool, got {type(rc).__name__}",
    )

    olb = packet["omission_load_bearing"]
    _require(
        isinstance(olb, bool),
        f"{pfx}: omission_load_bearing must be bool, got {type(olb).__name__}",
    )

    if is_v02:
        st = packet["severity_tier"]
        _require(
            st in SEVERITY_TIER_VALUES_ORDERED,
            f"{pfx}: severity_tier invalid: {st!r}",
            path="gsae_observation.severity_tier",
            expected=" | ".join(SEVERITY_TIER_VALUES_ORDERED),
            got=repr(st),
        )
    else:
        sts = packet["severity_toward_subject"]
        _require(
            sts in SEVERITY_TIER_VALUES_ORDERED,
            f"{pfx}: severity_toward_subject invalid: {sts!r}",
            path="gsae_observation.severity_toward_subject",
            expected=" | ".join(SEVERITY_TIER_VALUES_ORDERED),
            got=repr(sts),
        )
        stc = packet["severity_toward_counterparty"]
        _require(
            stc in SEVERITY_TIER_VALUES_ORDERED,
            f"{pfx}: severity_toward_counterparty invalid: {stc!r}",
            path="gsae_observation.severity_toward_counterparty",
            expected=" | ".join(SEVERITY_TIER_VALUES_ORDERED),
            got=repr(stc),
        )


def _validate_gsae_subject(subject: Dict[str, Any]) -> None:
    pfx = "_validate_gsae_subject"
    _require(isinstance(subject, dict), f"{pfx}: subject must be dict")

    keys = set(subject.keys())
    _require(
        keys == GSAE_SUBJECT_REQUIRED_KEYS,
        f"{pfx}: key mismatch — "
        f"missing={sorted(GSAE_SUBJECT_REQUIRED_KEYS - keys)}, "
        f"extra={sorted(keys - GSAE_SUBJECT_REQUIRED_KEYS)}",
    )

    for k in sorted(GSAE_SUBJECT_REQUIRED_KEYS):
        val = subject[k]
        _require(
            isinstance(val, str) and val.strip(),
            f"{pfx}: {k} must be non-empty str, got {type(val).__name__}",
        )


def _validate_gsae_settings(settings: Dict[str, Any]) -> None:
    pfx = "_validate_gsae_settings"
    _require(isinstance(settings, dict), f"{pfx}: settings must be dict")

    keys = set(settings.keys())
    _require(
        keys == GSAE_SETTINGS_REQUIRED_KEYS,
        f"{pfx}: key mismatch — "
        f"missing={sorted(GSAE_SETTINGS_REQUIRED_KEYS - keys)}, "
        f"extra={sorted(keys - GSAE_SETTINGS_REQUIRED_KEYS)}",
    )

    _require(
        isinstance(settings["enabled"], bool),
        f"{pfx}: enabled must be bool",
    )

    eps = settings["epsilon"]
    _require(
        _is_numeric_not_bool(eps),
        f"{pfx}: epsilon must be numeric (int/float), got {type(eps).__name__}",
    )

    tau = settings["tau"]
    _require(
        _is_numeric_not_bool(tau),
        f"{pfx}: tau must be numeric (int/float), got {type(tau).__name__}",
    )

    _require(eps >= 0, f"{pfx}: epsilon must be >= 0, got {eps}")
    _require(tau >= eps, f"{pfx}: tau must be >= epsilon ({eps}), got {tau}")

    ver = settings["version"]
    _require(
        isinstance(ver, str) and ver.strip(),
        f"{pfx}: version must be non-empty str",
    )

    weights = settings["weights"]
    _require(isinstance(weights, dict), f"{pfx}: weights must be dict")

    if ver == "0.3":
        expected_w_keys = GSAE_SYMMETRY_PACKET_V03_REQUIRED_KEYS
    else:
        expected_w_keys = GSAE_SYMMETRY_PACKET_REQUIRED_KEYS

    w_keys = set(weights.keys())
    _require(
        w_keys == expected_w_keys,
        f"{pfx}: weights key mismatch for version {ver!r} — "
        f"missing={sorted(expected_w_keys - w_keys)}, "
        f"extra={sorted(w_keys - expected_w_keys)}",
    )
    for wk, wv in weights.items():
        _require(
            _is_numeric_not_bool(wv),
            f"{pfx}: weights[{wk!r}] must be numeric (int/float), got {type(wv).__name__}",
        )
        _require(
            wv >= 0,
            f"{pfx}: weights[{wk!r}] must be >= 0, got {wv}",
        )


def _validate_gsae_symmetry_artifact(artifact: Dict[str, Any]) -> None:
    pfx = "_validate_gsae_symmetry_artifact"
    _require(isinstance(artifact, dict), f"{pfx}: artifact must be dict")

    keys = set(artifact.keys())
    _require(
        keys == GSAE_ARTIFACT_REQUIRED_KEYS,
        f"{pfx}: key mismatch — "
        f"missing={sorted(GSAE_ARTIFACT_REQUIRED_KEYS - keys)}, "
        f"extra={sorted(keys - GSAE_ARTIFACT_REQUIRED_KEYS)}",
    )

    status = artifact["symmetry_status"]
    _require(
        status in SYMMETRY_STATUS_VALUES,
        f"{pfx}: symmetry_status invalid: {status!r}",
    )

    delta = artifact["delta"]
    if status == "UNKNOWN":
        _require(
            delta is None,
            f"{pfx}: delta must be None when symmetry_status is UNKNOWN",
        )
    else:
        _require(
            _is_numeric_not_bool(delta),
            f"{pfx}: delta must be numeric when symmetry_status is {status!r}, "
            f"got {type(delta).__name__}",
        )

    eps = artifact["epsilon"]
    _require(
        _is_numeric_not_bool(eps),
        f"{pfx}: epsilon must be numeric (int/float), got {type(eps).__name__}",
    )

    tau = artifact["tau"]
    _require(
        _is_numeric_not_bool(tau),
        f"{pfx}: tau must be numeric (int/float), got {type(tau).__name__}",
    )

    flag = artifact["soft_symmetry_flag"]
    _require(isinstance(flag, bool), f"{pfx}: soft_symmetry_flag must be bool")

    if status in ("UNKNOWN", "PASS"):
        _require(
            flag is False,
            f"{pfx}: soft_symmetry_flag must be False when symmetry_status is {status!r}",
        )
    else:
        _require(
            flag is True,
            f"{pfx}: soft_symmetry_flag must be True when symmetry_status is {status!r}",
        )

    qf = artifact["quarantine_fields"]
    _require(isinstance(qf, list), f"{pfx}: quarantine_fields must be list")
    for i, f_name in enumerate(qf):
        _require(
            isinstance(f_name, str),
            f"{pfx}: quarantine_fields[{i}] must be str",
        )
        _require(
            f_name in SYMMETRY_FIELDS_ALL,
            f"{pfx}: quarantine_fields[{i}] invalid field: {f_name!r}",
        )

    if status != "QUARANTINE":
        _require(
            len(qf) == 0,
            f"{pfx}: quarantine_fields must be empty when symmetry_status is {status!r}",
        )

    fd = artifact["field_deltas"]
    _require(isinstance(fd, dict), f"{pfx}: field_deltas must be dict")
    for fk, fv in fd.items():
        _require(
            fk in SYMMETRY_FIELDS_ALL,
            f"{pfx}: field_deltas key {fk!r} not in SYMMETRY_FIELDS_ALL",
        )
        if fv is not None:
            _require(
                _is_numeric_not_bool(fv),
                f"{pfx}: field_deltas[{fk!r}] must be numeric or None, "
                f"got {type(fv).__name__}",
            )

    notes = artifact["notes"]
    _require(isinstance(notes, list), f"{pfx}: notes must be list")
    for i, n in enumerate(notes):
        _require(
            isinstance(n, str) and n.strip(),
            f"{pfx}: notes[{i}] must be non-empty str",
        )


# ---------------------------------------------------------------------------
# validate_run
# ---------------------------------------------------------------------------


def validate_run(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    _require("phase2" in run_state, "run_state missing phase2")
    phase2 = run_state["phase2"]
    _require(isinstance(phase2, dict), "run_state.phase2 must be dict")

    ev = run_state.get("evidence_bank", {})
    items = ev.get("items", [])
    _require(isinstance(items, list), "run_state.evidence_bank.items must be list")

    valid_eids = {it.get("eid") for it in items if isinstance(it, dict) and it.get("eid")}
    _require(len(valid_eids) > 0, "EvidenceBank has no valid eids")

    # Inject canonical EIDs so validate_reviewer_pack → normalize_reviewer_pack
    # can strip hallucinated EIDs before the global integrity check.
    config["_available_eids"] = valid_eids

    normalized_text: str | None = run_state.get("normalized_text")
    _validate_evidence_bank_items(items, normalized_text)

    enabled = config.get("reviewers_enabled", [])
    _require(
        isinstance(enabled, list) and len(enabled) > 0,
        "config.reviewers_enabled must be a non-empty list",
    )

    expected = []
    for x in enabled:
        _require(isinstance(x, str) and x.strip(), "config.reviewers_enabled entries must be non-empty strings")
        expected.append(x.strip())

    # Tolerate partial reviewer sets: the pipeline's min_reviewers gate already
    # ensures enough reviewers completed.  Only validate packs that exist.
    min_rev = min(int(config.get("min_reviewers_required", 2)), len(expected))
    present = [name for name in expected if name in phase2]
    _require(
        len(present) >= min_rev,
        f"phase2 has {len(present)} reviewer outputs ({present}), "
        f"but min_reviewers_required={min_rev}",
    )

    # Per-reviewer normalization (includes Layer 7 EID sanitization) BEFORE global check.
    for name in present:
        validate_reviewer_pack(phase2[name], config)

    # Safety-net: strip bad EIDs from adjudicated dict (built before validate_run runs).
    _strip_bad_eids(run_state.get("adjudicated", {}), valid_eids)

    # Global EID integrity check — now runs AFTER sanitization.
    referenced: List[str] = []
    _collect_eids(run_state.get("phase2", {}), referenced)
    _collect_eids(run_state.get("adjudicated", {}), referenced)

    bad = sorted({
        eid.strip() for eid in referenced
        if isinstance(eid, str) and eid.strip() and eid.strip() not in valid_eids
    })
    if bad:
        raise RuntimeError(f"EID integrity failure: referenced but not in EvidenceBank: {bad}")

    claim_registry: Set[str] = set()
    for name in present:
        pack = phase2[name]
        for claim in list_triage_claims(pack):
            cid = claim.get("claim_id")
            if isinstance(cid, str) and cid.strip():
                claim_registry.add(cid)

    _validate_near_duplicate_refs(phase2, claim_registry)

    _validate_verification(run_state, config)
    _validate_gsae_run_state(run_state)


# ---------------------------------------------------------------------------
# GSAE run_state orchestration
# ---------------------------------------------------------------------------


def _validate_gsae_run_state(run_state: Dict[str, Any]) -> None:
    pfx = "_validate_gsae_run_state"
    gsae = run_state.get("gsae")
    if gsae is None:
        return

    _require(isinstance(gsae, dict), f"{pfx}: run_state.gsae must be dict")

    settings = gsae.get("settings")
    _require(settings is not None, f"{pfx}: run_state.gsae.settings missing")
    _validate_gsae_settings(settings)

    pairs = gsae.get("packet_pairs")
    if pairs is not None:
        _require(isinstance(pairs, list), f"{pfx}: run_state.gsae.packet_pairs must be list")
        for i, pair in enumerate(pairs):
            _require(isinstance(pair, dict), f"{pfx}: packet_pairs[{i}] must be dict")
            _require("packet_a" in pair, f"{pfx}: packet_pairs[{i}] missing packet_a")
            _require("packet_b" in pair, f"{pfx}: packet_pairs[{i}] missing packet_b")
            _validate_gsae_symmetry_packet(pair["packet_a"])
            _validate_gsae_symmetry_packet(pair["packet_b"])

    artifacts = gsae.get("artifacts")
    if artifacts is not None:
        _require(isinstance(artifacts, list), f"{pfx}: run_state.gsae.artifacts must be list")
        for art in artifacts:
            _validate_gsae_symmetry_artifact(art)


# ---------------------------------------------------------------------------
# Verification layer validation
# ---------------------------------------------------------------------------


def _validate_verification(run_state: Dict[str, Any], config: Dict[str, Any]) -> None:
    from engine.verify.base import (  # local import: verify layer is optional
        CLAIM_KINDS,
        CONFIDENCE_VALUES as VERIFY_CONFIDENCE_VALUES,
        SOURCE_TYPES,
        VERIFICATION_STATUSES,
    )

    verification_enabled = bool(config.get("verification_enabled", False))
    pack = run_state.get("verification")

    if not verification_enabled:
        if pack is None:
            return
        _require(isinstance(pack, dict), "run_state.verification must be dict when present")
        enabled_flag = pack.get("enabled")
        if enabled_flag is not None:
            _require(
                enabled_flag is False,
                "run_state.verification.enabled must be False when verification_enabled=false",
            )
        return

    _require(pack is not None, "run_state.verification missing but verification_enabled=true")
    _require(isinstance(pack, dict), "run_state.verification must be dict")
    _require(
        pack.get("enabled") is True,
        "run_state.verification.enabled must be True when verification_enabled=true",
    )

    results = pack.get("results")
    _require(isinstance(results, list), "run_state.verification.results must be list")

    kinds_enabled_raw = config.get("verification_kinds_enabled", list(CLAIM_KINDS))
    _require(isinstance(kinds_enabled_raw, list), "config.verification_kinds_enabled must be a list")
    kinds_enabled: set[str] = set()
    for k in kinds_enabled_raw:
        _require(
            k in CLAIM_KINDS,
            f"config.verification_kinds_enabled contains unknown kind: {k!r}",
        )
        kinds_enabled.add(k)

    seen_ids: set[str] = set()

    for i, r in enumerate(results):
        _require(isinstance(r, dict), f"verification result[{i}] must be dict")

        claim_id = r.get("claim_id")
        _require(
            isinstance(claim_id, str) and claim_id.strip(),
            f"verification result[{i}].claim_id must be a non-empty string",
        )
        _require(
            claim_id not in seen_ids,
            f"duplicate claim_id in verification results: {claim_id!r}",
        )
        seen_ids.add(claim_id)

        claim_text = r.get("claim_text")
        _require(
            isinstance(claim_text, str) and claim_text.strip(),
            f"verification result[{i}].claim_text must be non-empty",
        )

        claim_kind = r.get("claim_kind")
        _require(
            claim_kind in CLAIM_KINDS,
            f"verification result[{i}].claim_kind invalid: {claim_kind!r}",
        )

        status = r.get("verification_status")
        _require(
            status in VERIFICATION_STATUSES,
            f"verification result[{i}].verification_status invalid: {status!r}",
        )

        confidence = r.get("confidence")
        if isinstance(confidence, str) and confidence.upper() in VERIFY_CONFIDENCE_VALUES:
            confidence = confidence.upper()
            r["confidence"] = confidence
        _require(
            confidence in VERIFY_CONFIDENCE_VALUES,
            f"verification result[{i}].confidence invalid: {confidence!r}",
        )

        method_note = r.get("method_note")
        _require(
            isinstance(method_note, str) and method_note.strip(),
            f"verification result[{i}].method_note must be non-empty",
        )

        checked_at = r.get("checked_at")
        _require(
            isinstance(checked_at, str) and checked_at.strip(),
            f"verification result[{i}].checked_at must be non-empty",
        )

        authority_sources = r.get("authority_sources")
        _require(
            isinstance(authority_sources, list),
            f"verification result[{i}].authority_sources must be list",
        )

        if status not in AUTHORITY_SOURCES_EXEMPT_STATUSES:
            _require(
                len(authority_sources) > 0,
                f"verification result[{i}].authority_sources must be non-empty when status={status!r}",
            )

        for j, src in enumerate(authority_sources):
            _require(
                isinstance(src, dict),
                f"verification result[{i}].authority_sources[{j}] must be dict",
            )
            src_type = src.get("source_type")
            _require(
                src_type in SOURCE_TYPES,
                f"verification result[{i}].authority_sources[{j}].source_type invalid: {src_type!r}",
            )
            has_locator = isinstance(src.get("locator"), str) and bool(src["locator"].strip())
            has_url = isinstance(src.get("url"), str) and bool(src["url"].strip())
            _require(
                has_locator or has_url,
                f"verification result[{i}].authority_sources[{j}] must have locator or url",
            )
