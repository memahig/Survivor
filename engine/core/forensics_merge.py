#!/usr/bin/env python3
"""
FILE: engine/core/forensics_merge.py
VERSION: 0.1
PURPOSE:
Merge structural forensics findings across reviewers into provenance-preserving
aggregated objects.

CONTRACT:
- Pure function, no I/O, deterministic.
- Conservative grouping: only merge when normalized text matches exactly.
- Every merged object preserves supporting_reviewers and confidence_by_reviewer.
- concern_level: 1 reviewer → low, 2 → elevated, 3+ → high.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Text normalization (conservative — exact match after cleanup)
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation edges."""
    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(".,;:!?")
    return s


# ---------------------------------------------------------------------------
# Concern level rule
# ---------------------------------------------------------------------------

def _concern_level(n_reviewers: int) -> str:
    if n_reviewers <= 1:
        return "low"
    if n_reviewers == 2:
        return "elevated"
    return "high"


# ---------------------------------------------------------------------------
# Claim omissions — merge by target_claim_id
# ---------------------------------------------------------------------------

def _merge_claim_omissions(
    packs: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group claim_omissions across reviewers by target_claim_id.
    Within a target, sub-group by normalized missing_frame.
    """
    # bucket: target_claim_id -> norm(missing_frame) -> list of (reviewer, entry)
    buckets: Dict[str, Dict[str, List[tuple]]] = {}

    for reviewer, pack in packs.items():
        for item in pack.get("claim_omissions", []):
            tcid = item.get("target_claim_id", "")
            mf = item.get("missing_frame", "")
            key = _norm(mf)
            buckets.setdefault(tcid, {}).setdefault(key, []).append((reviewer, item))

    results: List[Dict[str, Any]] = []
    for tcid in sorted(buckets):
        for _nf_key, entries in sorted(buckets[tcid].items()):
            reviewers = sorted(set(r for r, _ in entries))
            conf_by = {r: e.get("confidence", "medium") for r, e in entries}
            # Use the longest missing_frame as merged_text (most descriptive)
            merged_text = max((e.get("missing_frame", "") for _, e in entries), key=len)
            reason = max((e.get("reason_expected", "") for _, e in entries), key=len)

            results.append({
                "kind": "claim_omission",
                "target_claim_id": tcid,
                "merged_text": merged_text,
                "reason_expected": reason,
                "supporting_reviewers": reviewers,
                "confidence_by_reviewer": conf_by,
                "concern_level": _concern_level(len(reviewers)),
            })

    return results


# ---------------------------------------------------------------------------
# Article omissions — merge by normalized missing_frame (conservative)
# ---------------------------------------------------------------------------

def _merge_article_omissions(
    packs: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # bucket: norm(missing_frame) -> list of (reviewer, entry)
    buckets: Dict[str, List[tuple]] = {}

    for reviewer, pack in packs.items():
        for item in pack.get("article_omissions", []):
            mf = item.get("missing_frame", "")
            key = _norm(mf)
            buckets.setdefault(key, []).append((reviewer, item))

    results: List[Dict[str, Any]] = []
    for _key in sorted(buckets):
        entries = buckets[_key]
        reviewers = sorted(set(r for r, _ in entries))
        conf_by = {r: e.get("confidence", "medium") for r, e in entries}
        merged_text = max((e.get("missing_frame", "") for _, e in entries), key=len)
        reason = max((e.get("reason_expected", "") for _, e in entries), key=len)

        # Union of affected_claim_ids across reviewers
        all_ids: set = set()
        for _, e in entries:
            for cid in e.get("affected_claim_ids", []):
                all_ids.add(cid)

        results.append({
            "kind": "article_omission",
            "merged_text": merged_text,
            "reason_expected": reason,
            "supporting_reviewers": reviewers,
            "confidence_by_reviewer": conf_by,
            "affected_claim_ids": sorted(all_ids),
            "concern_level": _concern_level(len(reviewers)),
        })

    return results


# ---------------------------------------------------------------------------
# Framing omissions — merge by normalized missing_frame (conservative)
# ---------------------------------------------------------------------------

def _merge_framing_omissions(
    packs: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # bucket: norm(missing_frame) -> list of (reviewer, entry)
    buckets: Dict[str, List[tuple]] = {}

    for reviewer, pack in packs.items():
        for item in pack.get("framing_omissions", []):
            mf = item.get("missing_frame", "")
            key = _norm(mf)
            buckets.setdefault(key, []).append((reviewer, item))

    results: List[Dict[str, Any]] = []
    for _key in sorted(buckets):
        entries = buckets[_key]
        reviewers = sorted(set(r for r, _ in entries))
        conf_by = {r: e.get("confidence", "medium") for r, e in entries}
        merged_text = max((e.get("missing_frame", "") for _, e in entries), key=len)
        reason = max((e.get("reason_expected", "") for _, e in entries), key=len)
        frame_used = max((e.get("frame_used_by_article", "") for _, e in entries), key=len)

        # Union of alternative_frames across reviewers
        all_frames: set = set()
        for _, e in entries:
            for f in e.get("alternative_frames", []):
                if isinstance(f, str):
                    all_frames.add(f)

        results.append({
            "kind": "framing_omission",
            "frame_used_by_article": frame_used,
            "merged_text": merged_text,
            "reason_expected": reason,
            "supporting_reviewers": reviewers,
            "confidence_by_reviewer": conf_by,
            "alternative_frames": sorted(all_frames),
            "concern_level": _concern_level(len(reviewers)),
        })

    return results


# ---------------------------------------------------------------------------
# Argument summary — merge into multi-reviewer view
# ---------------------------------------------------------------------------

def _merge_argument_summaries(
    packs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:
    """
    Collect argument_summary from each reviewer that has one.
    Return a dict with per-reviewer summaries preserved, plus a union
    of key_rival_explanations_missing across reviewers.
    """
    summaries: Dict[str, Dict[str, Any]] = {}
    for reviewer, pack in packs.items():
        s = pack.get("argument_summary")
        if isinstance(s, dict):
            summaries[reviewer] = s

    if not summaries:
        return None

    # Union of missing rival explanations (dedupe by normalized text)
    seen: Dict[str, str] = {}  # norm -> original
    for s in summaries.values():
        for rival in s.get("key_rival_explanations_missing", []):
            n = _norm(rival)
            # Keep the longer original form
            if n not in seen or len(rival) > len(seen[n]):
                seen[n] = rival

    return {
        "by_reviewer": summaries,
        "merged_rival_explanations_missing": sorted(seen.values()),
        "supporting_reviewers": sorted(summaries.keys()),
    }


# ---------------------------------------------------------------------------
# Object discipline — merge into multi-reviewer view
# ---------------------------------------------------------------------------

def _merge_object_discipline(
    packs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:
    checks: Dict[str, Dict[str, Any]] = {}
    for reviewer, pack in packs.items():
        odc = pack.get("object_discipline_check")
        if isinstance(odc, dict):
            checks[reviewer] = odc

    if not checks:
        return None

    any_fail = any(c.get("status") == "fail" for c in checks.values())

    return {
        "by_reviewer": checks,
        "overall_status": "fail" if any_fail else "pass",
        "supporting_reviewers": sorted(checks.keys()),
    }


# ---------------------------------------------------------------------------
# Rival narratives — merge by normalized lens (conservative)
# ---------------------------------------------------------------------------

def _merge_rival_narratives(
    packs: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group rival_narratives across reviewers by normalized lens text.
    Conservative: only merge when normalized lens matches exactly.
    """
    # bucket: norm(lens) -> list of (reviewer, entry)
    buckets: Dict[str, List[tuple]] = {}

    for reviewer, pack in packs.items():
        for item in pack.get("rival_narratives", []):
            if not isinstance(item, dict):
                continue
            lens = item.get("lens", "")
            key = _norm(lens)
            if key:
                buckets.setdefault(key, []).append((reviewer, item))

    results: List[Dict[str, Any]] = []
    for _key in sorted(buckets):
        entries = buckets[_key]
        reviewers = sorted(set(r for r, _ in entries))
        conf_by = {r: e.get("confidence", "medium") for r, e in entries}
        # Use the longest lens and summary as canonical
        merged_lens = max((e.get("lens", "") for _, e in entries), key=len)
        merged_summary = max((e.get("summary", "") for _, e in entries), key=len)

        # Union of same_core_facts_used and claims_weakened_if_true
        all_facts: set = set()
        all_weakened: set = set()
        for _, e in entries:
            for f in e.get("same_core_facts_used", []):
                if isinstance(f, str):
                    all_facts.add(f)
            for c in e.get("claims_weakened_if_true", []):
                if isinstance(c, str):
                    all_weakened.add(c)

        # Use the highest structural_fragility across reviewers
        frag_order = {"low": 0, "elevated": 1, "high": 2}
        best_frag = max(
            (e.get("structural_fragility", "low") for _, e in entries),
            key=lambda x: frag_order.get(x, 0),
        )

        results.append({
            "kind": "rival_narrative",
            "lens": merged_lens,
            "merged_summary": merged_summary,
            "same_core_facts_used": sorted(all_facts),
            "claims_weakened_if_true": sorted(all_weakened),
            "structural_fragility": best_frag,
            "supporting_reviewers": reviewers,
            "confidence_by_reviewer": conf_by,
            "concern_level": _concern_level(len(reviewers)),
        })

    return results


# ---------------------------------------------------------------------------
# Shared blind spot check — corpus lock detection
# ---------------------------------------------------------------------------

def _shared_blind_spot_check(
    packs: Dict[str, Dict[str, Any]],
    merged_rivals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Detect corpus-locked blind spots.
    If ALL reviewers failed to construct any rival narrative, flag as fail.
    """
    reviewer_count = len(packs)
    if reviewer_count == 0:
        return {
            "status": "pass",
            "reason": "No reviewers present.",
        }

    # Check if ANY reviewer produced at least one rival narrative
    any_rival = any(
        len(pack.get("rival_narratives", [])) > 0
        for pack in packs.values()
    )

    if not any_rival:
        return {
            "status": "fail",
            "reason": (
                "No reviewer constructed a rival narrative. "
                "Possible corpus-locked blind spot."
            ),
        }

    # Count distinct lenses across merged rivals
    lens_count = len(merged_rivals)
    return {
        "status": "pass",
        "reason": (
            f"{lens_count} rival narrative(s) constructed across "
            f"{reviewer_count} reviewers."
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_structural_forensics(
    phase2_outputs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Merge structural forensics findings across all reviewer packs.

    Returns a dict with:
      - claim_omissions: merged list
      - article_omissions: merged list
      - framing_omissions: merged list
      - rival_narratives: merged list
      - shared_blind_spot_check: dict with status + reason
      - argument_summary: merged or None
      - object_discipline_check: merged or None
    """
    result: Dict[str, Any] = {
        "claim_omissions": _merge_claim_omissions(phase2_outputs),
        "article_omissions": _merge_article_omissions(phase2_outputs),
        "framing_omissions": _merge_framing_omissions(phase2_outputs),
    }

    merged_rivals = _merge_rival_narratives(phase2_outputs)
    result["rival_narratives"] = merged_rivals
    result["shared_blind_spot_check"] = _shared_blind_spot_check(
        phase2_outputs, merged_rivals,
    )

    arg_summary = _merge_argument_summaries(phase2_outputs)
    if arg_summary is not None:
        result["argument_summary"] = arg_summary

    obj_discipline = _merge_object_discipline(phase2_outputs)
    if obj_discipline is not None:
        result["object_discipline_check"] = obj_discipline

    return result
