#!/usr/bin/env python3
"""
FILE: engine/report/generator.py
VERSION: 0.1.1
PURPOSE:
Render a deterministic, structured JSON report from run_state + judge output.
Milestone R1 — structured JSON output only; no HTML/PDF.

CONTRACT:
- No I/O, no side effects, no narrative smoothing.
- Deterministic: identical inputs produce identical output.
- group text is canonical_text from judge or None — never rewritten.
- Evidence snippets are verbatim from EvidenceBank (quote + locator + source_id).
- Fail-closed: missing/malformed required keys raise RuntimeError (no KeyError escape).
- meta section omitted entirely when none of run_id/created_at/version are present.
- flags key omitted from group dict when flags list is empty.
- Unknown EIDs referenced by evidence_union are skipped gracefully in evidence_snippets.

REQUIRED INPUTS:
  run_state must include:
    evidence_bank       — dict with "items" list
    phase2              — dict (presence required; generator does not interpret packs)
    adjudicated_claims  — list of group dicts from engine.arena.judge.adjudicate()

OUTPUT SCHEMA:
  {
    "meta"?: { "run_id"?: str, "created_at"?: str, "version"?: str },
    "summary": {
      "overall_status":        str,          # rejected|downgraded|kept|insufficient
      "counts_by_status":      {str: int},   # sorted keys
      "high_risk_flags_count": int,
    },
    "groups": [
      {
        "group_id":               str,
        "member_claim_ids":       [str, ...],  # sorted
        "canonical_text":         str | None,
        "status":                 str,
        "wscore":                 float,
        "evidence_union":         [str, ...],  # sorted
        "evidence_snippets": [
          {"eid": str, "quote": str, "locator": dict, "source_id": str}, ...
        ],
        "contributing_reviewers": [str, ...],  # sorted
        "flags"?:                 [str, ...],  # only when non-empty
      },
      ...
    ],
    "appendix": {
      "evidence_index": [{"eid","quote","locator","source_id"}, ...],  # sorted by eid
      "reviewer_index": [{"reviewer","model_weight","notes"?}, ...],   # sorted by reviewer
    }
  }

OVERALL_STATUS priority (worst-case):
  rejected > downgraded > kept > insufficient
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_META_KEYS = ("run_id", "created_at", "version")

# Priority order for overall_status (index 0 = worst)
_STATUS_PRIORITY = ("rejected", "downgraded", "kept", "insufficient")


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _compute_overall_status(counts_by_status: Dict[str, int]) -> str:
    """
    Returns worst-case status across all groups.
    Priority: rejected > downgraded > kept > insufficient.
    Returns "insufficient" when no groups exist.
    """
    for status in _STATUS_PRIORITY:
        if counts_by_status.get(status, 0) > 0:
            return status
    if counts_by_status:
        return sorted(counts_by_status.keys())[0]
    return "insufficient"


def _validate_evidence_item(item: Any, idx: int) -> Dict[str, Any]:
    """
    Fail-closed validation for an EvidenceBank item.
    Returns the item dict (typed) if valid.
    """
    _require(isinstance(item, dict), f"EvidenceBank item[{idx}] must be dict")

    eid = item.get("eid")
    quote = item.get("quote")
    locator = item.get("locator")
    source_id = item.get("source_id")

    _require(isinstance(eid, str) and eid, f"EvidenceBank item[{idx}].eid must be non-empty str")
    _require(isinstance(quote, str) and quote, f"EvidenceBank item[{idx}] ({eid}): quote must be non-empty str")
    _require(isinstance(locator, dict), f"EvidenceBank item[{idx}] ({eid}): locator must be dict")
    _require(
        isinstance(source_id, str) and source_id,
        f"EvidenceBank item[{idx}] ({eid}): source_id must be non-empty str",
    )

    # We do NOT enforce locator subfields here (validators.py does that).
    # Generator only needs locator to be a dict for click-to-verify wiring.
    return item


def _validate_group(grp: Any, idx: int) -> Dict[str, Any]:
    """
    Fail-closed validation for one adjudicated group dict.
    """
    _require(isinstance(grp, dict), f"adjudicated_claims[{idx}] must be dict")

    group_id = grp.get("group_id")
    _require(
        isinstance(group_id, str) and group_id,
        f"adjudicated_claims[{idx}].group_id must be non-empty str",
    )

    member_claim_ids = grp.get("member_claim_ids")
    _require(
        isinstance(member_claim_ids, list),
        f"adjudicated_claims[{idx}] ({group_id}): member_claim_ids must be list",
    )
    _require(
        all(isinstance(x, str) for x in member_claim_ids),
        f"adjudicated_claims[{idx}] ({group_id}): member_claim_ids must be list[str]",
    )

    evidence_union = grp.get("evidence_union")
    _require(
        isinstance(evidence_union, list),
        f"adjudicated_claims[{idx}] ({group_id}): evidence_union must be list",
    )
    _require(
        all(isinstance(x, str) for x in evidence_union),
        f"adjudicated_claims[{idx}] ({group_id}): evidence_union must be list[str]",
    )

    contributing_reviewers = grp.get("contributing_reviewers")
    _require(
        isinstance(contributing_reviewers, list),
        f"adjudicated_claims[{idx}] ({group_id}): contributing_reviewers must be list",
    )
    _require(
        all(isinstance(x, str) for x in contributing_reviewers),
        f"adjudicated_claims[{idx}] ({group_id}): contributing_reviewers must be list[str]",
    )

    canonical_text = grp.get("canonical_text")
    _require(
        canonical_text is None or isinstance(canonical_text, str),
        f"adjudicated_claims[{idx}] ({group_id}): canonical_text must be str or None",
    )

    status = grp.get("status")
    _require(
        isinstance(status, str) and status,
        f"adjudicated_claims[{idx}] ({group_id}): status must be non-empty str",
    )

    # wscore must be coercible to float (fail closed if not)
    raw_wscore = grp.get("wscore", 0.0)
    try:
        float(raw_wscore)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"adjudicated_claims[{idx}] ({group_id}): wscore is not numeric: {raw_wscore!r}"
        ) from exc

    flags = grp.get("flags", None)
    if flags is not None:
        _require(
            isinstance(flags, list),
            f"adjudicated_claims[{idx}] ({group_id}): flags must be list when present",
        )
        _require(
            all(isinstance(x, str) for x in flags),
            f"adjudicated_claims[{idx}] ({group_id}): flags must be list[str]",
        )

    return grp


def generate_report(run_state: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a deterministic structured JSON report.

    Raises RuntimeError if required run_state keys are missing or malformed.
    """
    _require(isinstance(run_state, dict), "run_state must be dict")
    _require(isinstance(config, dict), "config must be dict")

    # ------------------------------------------------------------------
    # Required run_state keys (fail-closed, no defaults)
    # ------------------------------------------------------------------
    ev = run_state.get("evidence_bank")
    _require(isinstance(ev, dict), "run_state must contain evidence_bank dict")

    phase2 = run_state.get("phase2")
    _require(isinstance(phase2, dict), "run_state must contain phase2 dict")

    adjudicated_claims = run_state.get("adjudicated_claims")
    _require(isinstance(adjudicated_claims, list), "run_state must contain adjudicated_claims list")

    # ------------------------------------------------------------------
    # EvidenceBank items validation + eid_map
    # ------------------------------------------------------------------
    ev_items = ev.get("items")
    _require(isinstance(ev_items, list), "run_state.evidence_bank.items must be list")

    eid_map: Dict[str, Dict[str, Any]] = {}
    validated_items: List[Dict[str, Any]] = []

    for i, item in enumerate(ev_items):
        it = _validate_evidence_item(item, i)
        validated_items.append(it)
        eid = it["eid"]
        # If duplicates exist, last write would be non-deterministic across sources;
        # but EvidenceBank is expected canonical upstream. Fail-closed here.
        _require(eid not in eid_map, f"EvidenceBank duplicate eid: {eid!r}")
        eid_map[eid] = it

    # ------------------------------------------------------------------
    # Validate adjudicated groups (pre-pass) + deterministic sort
    # ------------------------------------------------------------------
    validated_groups: List[Dict[str, Any]] = []
    for i, grp in enumerate(adjudicated_claims):
        validated_groups.append(_validate_group(grp, i))

    validated_groups_sorted = sorted(validated_groups, key=lambda g: g["group_id"])

    # ------------------------------------------------------------------
    # Meta (only present when at least one optional key exists)
    # ------------------------------------------------------------------
    meta: Dict[str, Any] = {}
    for key in _META_KEYS:
        val = run_state.get(key)
        if val is not None:
            meta[key] = val

    # ------------------------------------------------------------------
    # Build groups output + summary tallies
    # ------------------------------------------------------------------
    groups_out: List[Dict[str, Any]] = []
    counts_by_status: Dict[str, int] = {}
    high_risk_flags_count = 0

    for grp in validated_groups_sorted:
        group_id: str = grp["group_id"]

        member_claim_ids: List[str] = sorted(grp["member_claim_ids"])
        canonical_text: Optional[str] = grp.get("canonical_text")
        status: str = grp["status"]

        wscore = float(grp.get("wscore", 0.0))
        evidence_union: List[str] = sorted(grp["evidence_union"])
        contributing_reviewers: List[str] = sorted(grp["contributing_reviewers"])

        flags_raw = grp.get("flags") or []
        flags: List[str] = sorted(flags_raw) if flags_raw else []

        counts_by_status[status] = counts_by_status.get(status, 0) + 1
        if "high_structural_risk" in flags:
            high_risk_flags_count += 1

        evidence_snippets: List[Dict[str, Any]] = []
        for eid in evidence_union:
            item = eid_map.get(eid)
            if item is None:
                # Contract: unknown eids in evidence_union are skipped gracefully.
                continue
            # item is validated, so no KeyError escape is possible here.
            evidence_snippets.append(
                {
                    "eid": item["eid"],
                    "quote": item["quote"],
                    "locator": item["locator"],
                    "source_id": item["source_id"],
                }
            )

        g_out: Dict[str, Any] = {
            "group_id": group_id,
            "member_claim_ids": member_claim_ids,
            "canonical_text": canonical_text,
            "status": status,
            "wscore": wscore,
            "evidence_union": evidence_union,
            "evidence_snippets": evidence_snippets,
            "contributing_reviewers": contributing_reviewers,
        }
        if flags:
            g_out["flags"] = flags

        groups_out.append(g_out)

    summary: Dict[str, Any] = {
        "overall_status": _compute_overall_status(counts_by_status),
        "counts_by_status": dict(sorted(counts_by_status.items())),
        "high_risk_flags_count": high_risk_flags_count,
    }

    # ------------------------------------------------------------------
    # Appendix: evidence_index (all EvidenceBank items, sorted by eid)
    # ------------------------------------------------------------------
    evidence_index: List[Dict[str, Any]] = sorted(
        [
            {
                "eid": item["eid"],
                "quote": item["quote"],
                "locator": item["locator"],
                "source_id": item["source_id"],
            }
            for item in validated_items
        ],
        key=lambda x: x["eid"],
    )

    # ------------------------------------------------------------------
    # Appendix: reviewer_index (sorted by reviewer name)
    # ------------------------------------------------------------------
    enabled_reviewers_raw = config.get("reviewers_enabled", [])
    _require(isinstance(enabled_reviewers_raw, list), "config.reviewers_enabled must be list when present")

    enabled_reviewers: List[str] = sorted(r for r in enabled_reviewers_raw if isinstance(r, str))

    model_weights: Dict[str, Any] = config.get("model_weights", {})
    _require(isinstance(model_weights, dict), "config.model_weights must be dict when present")

    reviewer_notes: Dict[str, Any] = config.get("reviewer_notes", {})
    _require(isinstance(reviewer_notes, dict), "config.reviewer_notes must be dict when present")

    reviewer_index: List[Dict[str, Any]] = []
    for reviewer in enabled_reviewers:
        raw_w = model_weights.get(reviewer, 1.0)
        try:
            mw = float(raw_w)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"config.model_weights[{reviewer!r}] is not numeric: {raw_w!r}"
            ) from exc

        entry: Dict[str, Any] = {"reviewer": reviewer, "model_weight": mw}
        note = reviewer_notes.get(reviewer)
        if isinstance(note, str) and note:
            entry["notes"] = note
        reviewer_index.append(entry)

    appendix: Dict[str, Any] = {
        "evidence_index": evidence_index,
        "reviewer_index": reviewer_index,
    }

    # ------------------------------------------------------------------
    # Assemble report (meta omitted when empty)
    # ------------------------------------------------------------------
    report: Dict[str, Any] = {}
    if meta:
        report["meta"] = meta
    report["summary"] = summary
    report["groups"] = groups_out
    report["appendix"] = appendix
    return report
