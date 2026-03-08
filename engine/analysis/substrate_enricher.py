#!/usr/bin/env python3
"""
FILE: engine/analysis/substrate_enricher.py
PURPOSE: Orchestrate all analysis modules. Enrich run_state into
         enriched_substrate consumed by both renderers.
RULES: Never mutates run_state. Each module wrapped in try/except.
       A failing module stores {"error": str} for its key, does not block others.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _build_evidence_lookup(run_state: Dict[str, Any]) -> Dict[str, str]:
    """Build eid -> quote text from evidence_bank."""
    eb = run_state.get("evidence_bank")
    if not isinstance(eb, dict):
        return {}
    items = eb.get("items", [])
    if not isinstance(items, list):
        return {}
    lookup: Dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        eid = item.get("eid", "")
        # Use quote first, fall back to text
        quote = item.get("quote", "") or item.get("text", "")
        if isinstance(eid, str) and eid and isinstance(quote, str):
            lookup[eid] = quote
    return lookup


def _extract_adjudicated_claims(run_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract adjudicated_claims list from run_state."""
    adjudicated = run_state.get("adjudicated")
    if not isinstance(adjudicated, dict):
        return []
    claim_track = adjudicated.get("claim_track")
    if not isinstance(claim_track, dict):
        return []
    arena = claim_track.get("arena")
    if not isinstance(arena, dict):
        return []
    claims = arena.get("adjudicated_claims", [])
    return claims if isinstance(claims, list) else []


def _extract_structural_forensics(run_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structural_forensics dict from run_state."""
    adjudicated = run_state.get("adjudicated")
    if not isinstance(adjudicated, dict):
        return {}
    sf = adjudicated.get("structural_forensics")
    return sf if isinstance(sf, dict) else {}


def _extract_argument_integrity(
    structural_forensics: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Extract argument_integrity from structural_forensics."""
    ai = structural_forensics.get("argument_integrity")
    return ai if isinstance(ai, dict) else None


def _extract_whole_article_judgment(run_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract adjudicated_whole_article_judgment from run_state."""
    adjudicated = run_state.get("adjudicated")
    if not isinstance(adjudicated, dict):
        return {}
    article_track = adjudicated.get("article_track")
    if not isinstance(article_track, dict):
        return {}
    waj = article_track.get("adjudicated_whole_article_judgment")
    return waj if isinstance(waj, dict) else {}


def enrich_substrate(
    run_state: Dict[str, Any],
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Run all analysis modules on run_state, return enriched substrate.

    Never mutates run_state.
    Each module wrapped in try/except: failure → {"error": str} for that key.

    Call order:
    1. Build evidence_lookup
    2. causal_detections
    3. baseline_detections
    4. official_detections
    5. story_clusters
    6. load_bearing
    7. ranked_omissions (needs load_bearing output)
    8. reads_like (needs all above)
    9. priority_signals (needs all above)
    10. reader_interpretation (needs all above)
    11. peg_profile (post-interpretation consumer; does not perform signal detection)
    12. esm_profile (post-interpretation consumer; parallel to PEG, non-compensating)

    PEG and ESM are qualitative post-interpretation profile builders and do not
    perform signal detection.

    Returns dict with run_state keys passed through + derived analysis keys.
    """
    if config is None:
        config = {}

    # ---- Extract shared data ----
    evidence_lookup = _build_evidence_lookup(run_state)
    adjudicated_claims = _extract_adjudicated_claims(run_state)
    structural_forensics = _extract_structural_forensics(run_state)
    argument_integrity = _extract_argument_integrity(structural_forensics)
    whole_article_judgment = _extract_whole_article_judgment(run_state)

    # ---- Build base enriched substrate (passthrough + normalized keys) ----
    enriched: Dict[str, Any] = {
        # Raw passthrough for renderers that need full structure
        "article": run_state.get("article"),
        "evidence_bank": run_state.get("evidence_bank"),
        "phase1": run_state.get("phase1"),
        "phase2": run_state.get("phase2"),
        "adjudicated": run_state.get("adjudicated"),
        "gsae": run_state.get("gsae"),
        "divergence_radar": run_state.get("divergence_radar"),
        "verification": run_state.get("verification"),
        "metadata": run_state.get("metadata", {}),
        # Normalized top-level keys for renderers
        "evidence_lookup": evidence_lookup,
        "adjudicated_claims": adjudicated_claims,
        "structural_forensics": structural_forensics,
        "argument_integrity": argument_integrity,
        "adjudicated_whole_article_judgment": whole_article_judgment,
    }

    # ---- Module 1: Causal inference detector ----
    try:
        from engine.analysis.causal_inference_detector import detect_causal_claims
        enriched["causal_detections"] = detect_causal_claims(adjudicated_claims)
    except Exception as e:
        enriched["causal_detections"] = {"error": str(e)}

    # ---- Module 2: Baseline context detector ----
    try:
        from engine.analysis.baseline_context_detector import detect_baseline_absent
        enriched["baseline_detections"] = detect_baseline_absent(adjudicated_claims)
    except Exception as e:
        enriched["baseline_detections"] = {"error": str(e)}

    # ---- Module 3: Official assertion detector ----
    try:
        from engine.analysis.official_assertion_detector import detect_official_assertions
        enriched["official_detections"] = detect_official_assertions(
            adjudicated_claims, evidence_lookup
        )
    except Exception as e:
        enriched["official_detections"] = {"error": str(e)}

    # ---- Module 4: Claim deduplicator ----
    try:
        from engine.analysis.claim_deduplicator import cluster_story_claims
        threshold = config.get("story_cluster_jaccard_threshold", 0.25)
        enriched["story_clusters"] = cluster_story_claims(adjudicated_claims, threshold)
    except Exception as e:
        enriched["story_clusters"] = {"error": str(e)}

    # ---- Module 5: Load-bearing claims ----
    try:
        from engine.analysis.load_bearing_claims import identify_load_bearing
        enriched["load_bearing"] = identify_load_bearing(
            adjudicated_claims, argument_integrity
        )
    except Exception as e:
        enriched["load_bearing"] = {"error": str(e)}

    # ---- Module 6: Omission ranker (needs load_bearing) ----
    try:
        from engine.analysis.omission_ranker import rank_omissions
        lb_group_ids: List[str] = []
        lb_result = enriched.get("load_bearing")
        if isinstance(lb_result, dict) and "error" not in lb_result:
            lb_group_ids = lb_result.get("load_bearing_group_ids", [])
        enriched["ranked_omissions"] = rank_omissions(
            structural_forensics, lb_group_ids, adjudicated_claims
        )
    except Exception as e:
        enriched["ranked_omissions"] = {"error": str(e)}

    # ---- Module 7: Reads-like label (needs all above) ----
    try:
        from engine.analysis.reads_like_label import infer_reads_like
        enriched["reads_like"] = infer_reads_like(enriched)
    except Exception as e:
        enriched["reads_like"] = {"error": str(e)}

    # ---- Module 8: Signal prioritizer (needs all above) ----
    try:
        from engine.analysis.signal_prioritizer import prioritize_signals

        # Extract safe lists for inputs (handle error dicts)
        causal = enriched.get("causal_detections", [])
        if not isinstance(causal, list):
            causal = []
        baseline = enriched.get("baseline_detections", [])
        if not isinstance(baseline, list):
            baseline = []
        official = enriched.get("official_detections", [])
        if not isinstance(official, list):
            official = []
        omissions = enriched.get("ranked_omissions", [])
        if not isinstance(omissions, list):
            omissions = []
        lb = enriched.get("load_bearing", {})
        if not isinstance(lb, dict) or "error" in lb:
            lb = {}
        rl = enriched.get("reads_like", {})
        if not isinstance(rl, dict) or "error" in rl:
            rl = {}

        top_n = config.get("top_signals", 5)
        enriched["priority_signals"] = prioritize_signals(
            adjudicated_claims, omissions, causal, baseline, official,
            lb, rl, top_n=top_n,
        )
    except Exception as e:
        enriched["priority_signals"] = {"error": str(e)}

    # ---- Module 10: Reader interpretation (needs all above) ----
    try:
        from engine.analysis.reader_interpretation import interpret_for_reader
        enriched["reader_interpretation"] = interpret_for_reader(enriched)
    except Exception as e:
        enriched["reader_interpretation"] = {"error": str(e)}

    # ---- Module 11: Success signal detector (post-interpretation, pre-ESM) ----
    try:
        from engine.analysis.success_signal_detector import detect_success_signals
        enriched["success_blocks"] = detect_success_signals(enriched)
    except Exception as e:
        enriched["success_blocks"] = {"error": str(e)}

    # ---- Module 12: PEG profile (post-interpretation consumer) ----
    try:
        from engine.analysis.peg import build_peg_profile
        enriched["peg_profile"] = build_peg_profile(enriched)
    except Exception as e:
        enriched["peg_profile"] = {"error": str(e)}

    # ---- Module 13: ESM profile (post-interpretation consumer, parallel to PEG) ----
    try:
        from engine.analysis.epistemic_success import build_success_profile
        enriched["esm_profile"] = build_success_profile(enriched)
    except Exception as e:
        enriched["esm_profile"] = {"error": str(e)}

    return enriched
