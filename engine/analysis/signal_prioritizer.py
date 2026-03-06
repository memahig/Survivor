#!/usr/bin/env python3
"""
FILE: engine/analysis/signal_prioritizer.py
PURPOSE: Rank all forensic findings and select top signals for the Blunt Report.
         Uses weighted scoring table; deduplicates by source_id.
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


# ---- Scoring table ----

_SCORE_TABLE: Dict[str, float] = {
    "load_bearing_claim_rejected": 1.0,
    "load_bearing_claim_unsupported": 0.95,
    "omission_load_bearing": 0.9,
    "high_centrality_rejected": 0.85,
    "unsupported_causal": 0.7,
    "omission_important": 0.65,
    "baseline_absent": 0.55,
    "official_assertion_only": 0.5,
}


def _truncate(s: str, n: int = 120) -> str:
    s = str(s or "").strip()
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "\u2026"


def prioritize_signals(
    adjudicated_claims: List[Dict[str, Any]],
    ranked_omissions: List[Dict[str, Any]],
    causal_detections: List[Dict[str, Any]],
    baseline_detections: List[Dict[str, Any]],
    official_detections: List[Dict[str, Any]],
    load_bearing: Dict[str, Any],
    reads_like: Dict[str, Any],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Aggregate all signal types, score each, deduplicate, return top_n.

    Every summary is substrate-derived, not editorialized.

    Args:
        adjudicated_claims: from arena
        ranked_omissions: from omission_ranker
        causal_detections: from causal_inference_detector
        baseline_detections: from baseline_context_detector
        official_detections: from official_assertion_detector
        load_bearing: from load_bearing_claims
        reads_like: from reads_like_label (unused currently, reserved for future)
        top_n: max signals to return

    Returns list of signal dicts sorted by score descending.
    """
    # Collect all candidate signals: (signal_type, score, summary, source_id)
    candidates: List[Tuple[str, float, str, str]] = []

    lb_ids = set()
    if isinstance(load_bearing, dict):
        lb_ids = set(load_bearing.get("load_bearing_group_ids", []))

    # ---- Load-bearing claim signals ----
    if isinstance(adjudicated_claims, list):
        for claim in adjudicated_claims:
            if not isinstance(claim, dict):
                continue
            gid = claim.get("group_id", "")
            if not gid or gid not in lb_ids:
                continue

            adj = claim.get("adjudication", "")
            text = _truncate(claim.get("text", ""))

            if adj == "rejected":
                candidates.append((
                    "load_bearing_claim_rejected",
                    _SCORE_TABLE["load_bearing_claim_rejected"],
                    f"Load-bearing claim rejected: \"{text}\"",
                    gid,
                ))
            elif adj == "downgraded":
                candidates.append((
                    "load_bearing_claim_unsupported",
                    _SCORE_TABLE["load_bearing_claim_unsupported"],
                    f"Load-bearing claim downgraded: \"{text}\"",
                    gid,
                ))

    # ---- High-centrality rejected (non-load-bearing) ----
    if isinstance(adjudicated_claims, list):
        for claim in adjudicated_claims:
            if not isinstance(claim, dict):
                continue
            gid = claim.get("group_id", "")
            centrality = claim.get("centrality", 1)
            adj = claim.get("adjudication", "")

            if (
                isinstance(centrality, int)
                and centrality >= 3
                and adj == "rejected"
                and gid not in lb_ids
            ):
                text = _truncate(claim.get("text", ""))
                candidates.append((
                    "high_centrality_rejected",
                    _SCORE_TABLE["high_centrality_rejected"],
                    f"High-centrality claim rejected: \"{text}\"",
                    gid,
                ))

    # ---- Omission signals ----
    if isinstance(ranked_omissions, list):
        for i, om in enumerate(ranked_omissions):
            if not isinstance(om, dict):
                continue
            severity = om.get("severity", "minor")
            merged_text = _truncate(om.get("merged_text", ""))
            source_id = f"omission-{i}"

            if severity == "load_bearing":
                candidates.append((
                    "omission_load_bearing",
                    _SCORE_TABLE["omission_load_bearing"],
                    f"Load-bearing omission: {merged_text}",
                    source_id,
                ))
            elif severity == "important":
                candidates.append((
                    "omission_important",
                    _SCORE_TABLE["omission_important"],
                    f"Important omission: {merged_text}",
                    source_id,
                ))

    # ---- Unsupported causal signals ----
    if isinstance(causal_detections, list):
        for det in causal_detections:
            if not isinstance(det, dict):
                continue
            if not det.get("unsupported_causal"):
                continue
            gid = det.get("group_id", "")
            text = _truncate(det.get("claim_text", ""))
            candidates.append((
                "unsupported_causal",
                _SCORE_TABLE["unsupported_causal"],
                f"Unsupported causal claim: \"{text}\"",
                gid or f"causal-{len(candidates)}",
            ))

    # ---- Baseline absent signals ----
    if isinstance(baseline_detections, list):
        for det in baseline_detections:
            if not isinstance(det, dict):
                continue
            if not det.get("baseline_absent"):
                continue
            gid = det.get("group_id", "")
            text = _truncate(det.get("claim_text", ""))
            candidates.append((
                "baseline_absent",
                _SCORE_TABLE["baseline_absent"],
                f"Statistical claim without baseline: \"{text}\"",
                gid or f"baseline-{len(candidates)}",
            ))

    # ---- Official assertion signals ----
    if isinstance(official_detections, list):
        for det in official_detections:
            if not isinstance(det, dict):
                continue
            if not det.get("official_only"):
                continue
            gid = det.get("group_id", "")
            text = _truncate(det.get("claim_text", ""))
            candidates.append((
                "official_assertion_only",
                _SCORE_TABLE["official_assertion_only"],
                f"Claim relies only on official assertions: \"{text}\"",
                gid or f"official-{len(candidates)}",
            ))

    # ---- Deduplicate by source_id, keep highest score ----
    best_by_source: Dict[str, Tuple[str, float, str, str]] = {}
    for signal_type, score, summary, source_id in candidates:
        existing = best_by_source.get(source_id)
        if existing is None or score > existing[1]:
            best_by_source[source_id] = (signal_type, score, summary, source_id)

    # Sort by score descending, then by source_id for determinism
    sorted_signals = sorted(
        best_by_source.values(),
        key=lambda x: (-x[1], x[3]),
    )

    # Build output
    results: List[Dict[str, Any]] = []
    for rank, (signal_type, score, summary, source_id) in enumerate(sorted_signals[:top_n], 1):
        results.append({
            "rank": rank,
            "signal_type": signal_type,
            "score": score,
            "summary": summary,
            "source_id": source_id,
        })

    return results
