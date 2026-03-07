#!/usr/bin/env python3
"""
FILE: engine/analysis/reader_interpretation.py
PURPOSE: Translate structural signals into reader-facing mechanism explanations.
         Maps signal combinations to plain-language interpretation blocks.
         Every sentence is substrate-derived — no editorializing.
RULES: pure, deterministic, no I/O, fail-closed.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _sd(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _sl(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _s(x: Any) -> str:
    return str(x or "").strip()


def _trunc(s: str, n: int = 100) -> str:
    s = _s(s)
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "\u2026"


# ---------------------------------------------------------------------------
# Mechanism detectors — each returns a block dict or None
# ---------------------------------------------------------------------------

def _detect_unsupported_causal(enriched: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect unsupported causal claims — origin stories asserted without proof."""
    causal = _sl(enriched.get("causal_detections"))
    unsupported = [
        d for d in causal
        if isinstance(d, dict) and d.get("unsupported_causal") is True
    ]
    if not unsupported:
        return None

    examples = []
    for d in unsupported[:3]:
        text = _trunc(d.get("claim_text", ""))
        if text:
            examples.append(text)

    body_parts = [
        f"The article makes {len(unsupported)} causal claim(s) "
        f"without supporting evidence."
    ]
    if examples:
        body_parts.append(
            "These include claims about causes, origins, or consequences "
            "that are stated as fact but not demonstrated:"
        )
        for ex in examples:
            body_parts.append(f"- \"{ex}\"")
    body_parts.append(
        "When causal claims are asserted rather than demonstrated, "
        "they organize belief rather than evidence."
    )

    return {
        "mechanism": "unsupported_causal",
        "title": "It asserts causes without proving them",
        "body": "\n".join(body_parts),
        "source_signals": [
            {"type": "unsupported_causal", "count": len(unsupported)}
        ],
    }


def _detect_omission_dependence(enriched: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect omission-dependent reasoning — argument works because alternatives absent."""
    ranked = _sl(enriched.get("ranked_omissions"))
    significant = [
        om for om in ranked
        if isinstance(om, dict) and om.get("severity") in ("load_bearing", "important")
    ]
    if not significant:
        return None

    # Also check for rival narratives
    sf = _sd(enriched.get("structural_forensics"))
    rivals = _sl(sf.get("rival_narratives"))

    # Collect omission texts by kind
    article_omissions = [
        om for om in significant if om.get("kind") == "article_omission"
    ]
    framing_omissions = [
        om for om in significant if om.get("kind") == "framing_omission"
    ]
    claim_omissions = [
        om for om in significant if om.get("kind") == "claim_omission"
    ]

    body_parts = []
    body_parts.append(
        f"The article's argument depends on {len(significant)} significant "
        f"omission(s) — perspectives or context that are absent."
    )

    # Show what's missing
    shown = 0
    all_omissions = article_omissions + framing_omissions + claim_omissions
    if all_omissions:
        body_parts.append("The analysis found these gaps:")
        for om in all_omissions[:5]:
            text = _trunc(om.get("merged_text", ""), 120)
            severity = om.get("severity", "")
            if text:
                body_parts.append(f"- {text} [{severity}]")
                shown += 1

    if rivals:
        body_parts.append(
            f"\n{len(rivals)} rival explanation(s) exist that the article "
            f"does not engage with."
        )

    body_parts.append(
        "\nBecause these perspectives are absent, "
        "the article's framing becomes the only available lens. "
        "The argument works partly because alternatives are not present to test it."
    )

    return {
        "mechanism": "omission_dependence",
        "title": "It removes competing ways of understanding what's happening",
        "body": "\n".join(body_parts),
        "source_signals": [
            {"type": "omission_significant", "count": len(significant)},
            {"type": "rival_narratives", "count": len(rivals)},
        ],
    }


def _detect_framing_escalation(enriched: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect framing escalation — shift from analysis to alarm."""
    ranked = _sl(enriched.get("ranked_omissions"))
    framing_oms = [
        om for om in ranked
        if isinstance(om, dict) and om.get("kind") == "framing_omission"
        and om.get("severity") in ("load_bearing", "important")
    ]

    lb = _sd(enriched.get("load_bearing"))
    fragility = _s(lb.get("argument_fragility"))

    reads_like = _sd(enriched.get("reads_like"))
    flags = _sd(reads_like.get("flags"))

    has_reassurance = flags.get("has_reassurance_pattern", False)
    has_high_frag = flags.get("has_high_fragility", False)

    # Need framing omissions + at least one other escalation signal
    if not framing_oms and not (has_reassurance and has_high_frag):
        return None

    body_parts = []
    if framing_oms:
        body_parts.append(
            f"The article uses framing that excludes {len(framing_oms)} "
            f"alternative interpretation(s)."
        )
        for om in framing_oms[:3]:
            frame_used = _trunc(om.get("frame_used_by_article", ""), 80)
            missing = _trunc(om.get("merged_text", ""), 80)
            if frame_used and missing:
                body_parts.append(
                    f"- Frame used: \"{frame_used}\" — missing: \"{missing}\""
                )
            elif missing:
                body_parts.append(f"- Missing frame: \"{missing}\"")

    if has_high_frag:
        body_parts.append(
            f"Argument fragility is {fragility}. "
            "The framing escalates beyond what the evidence supports."
        )

    if not body_parts:
        return None

    body_parts.append(
        "When framing narrows and emotional intensity increases "
        "without proportional evidence, persuasion replaces demonstration."
    )

    return {
        "mechanism": "framing_escalation",
        "title": "It shifts from analysis into alarm",
        "body": "\n".join(body_parts),
        "source_signals": [
            {"type": "framing_omission", "count": len(framing_oms)},
            {"type": "high_fragility", "value": has_high_frag},
        ],
    }


def _detect_load_bearing_weakness(enriched: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect load-bearing weakness — biggest conclusions rest on weakest support."""
    lb = _sd(enriched.get("load_bearing"))
    if "error" in lb:
        return None

    lb_ids = set(_sl(lb.get("load_bearing_group_ids")))
    wl_ids = set(_sl(lb.get("weak_link_group_ids")))
    fragility = _s(lb.get("argument_fragility"))

    if not lb_ids:
        return None

    claims = _sl(enriched.get("adjudicated_claims"))

    # Find load-bearing claims that are weak (rejected, downgraded, or weak-link)
    weak_lb = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        gid = c.get("group_id", "")
        if gid not in lb_ids:
            continue
        adj = c.get("adjudication", "")
        is_weak_link = gid in wl_ids
        if adj in ("rejected", "downgraded") or is_weak_link:
            weak_lb.append(c)

    if not weak_lb and fragility != "high":
        return None

    body_parts = []
    body_parts.append(
        f"{len(lb_ids)} claim(s) carry the argument's weight."
    )

    if weak_lb:
        body_parts.append(
            f"Of these, {len(weak_lb)} are structurally weak:"
        )
        for c in weak_lb[:3]:
            text = _trunc(c.get("text", ""), 100)
            adj = c.get("adjudication", "kept")
            gid = c.get("group_id", "")
            is_wl = gid in wl_ids
            qualifier = adj
            if is_wl and adj == "kept":
                qualifier = "weak link"
            if text:
                body_parts.append(f"- \"{text}\" [{qualifier}]")

    if fragility in ("high", "elevated"):
        body_parts.append(
            f"\nArgument fragility: **{fragility}**. "
            "The most important conclusions depend on the least demonstrated claims."
        )

    return {
        "mechanism": "load_bearing_weakness",
        "title": "The biggest conclusions rest on the weakest support",
        "body": "\n".join(body_parts),
        "source_signals": [
            {"type": "load_bearing_count", "count": len(lb_ids)},
            {"type": "weak_load_bearing", "count": len(weak_lb)},
            {"type": "fragility", "value": fragility},
        ],
    }


def _detect_official_reliance(enriched: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect official-source reliance without independent verification."""
    official = _sl(enriched.get("official_detections"))
    official_only = [
        d for d in official
        if isinstance(d, dict) and d.get("official_only") is True
    ]
    if not official_only:
        return None

    body_parts = [
        f"{len(official_only)} claim(s) are supported only by official "
        f"or institutional sources, with no independent verification."
    ]
    for d in official_only[:3]:
        text = _trunc(d.get("claim_text", ""), 100)
        if text:
            body_parts.append(f"- \"{text}\"")

    body_parts.append(
        "When claims rest entirely on official assertions, "
        "the article transmits authority rather than evidence."
    )

    return {
        "mechanism": "official_reliance",
        "title": "It relies on official sources without independent verification",
        "body": "\n".join(body_parts),
        "source_signals": [
            {"type": "official_only", "count": len(official_only)}
        ],
    }


def _detect_baseline_absence(enriched: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect statistical claims without baselines."""
    baseline = _sl(enriched.get("baseline_detections"))
    absent = [
        d for d in baseline
        if isinstance(d, dict) and d.get("baseline_absent") is True
    ]
    if not absent:
        return None

    body_parts = [
        f"{len(absent)} statistical claim(s) lack baseline context — "
        f"numbers are presented without comparison points."
    ]
    for d in absent[:2]:
        text = _trunc(d.get("claim_text", ""), 100)
        if text:
            body_parts.append(f"- \"{text}\"")

    body_parts.append(
        "Statistics without baselines can make ordinary changes "
        "look extraordinary, or vice versa."
    )

    return {
        "mechanism": "baseline_absence",
        "title": "It presents numbers without comparison",
        "body": "\n".join(body_parts),
        "source_signals": [
            {"type": "baseline_absent", "count": len(absent)}
        ],
    }


def _detect_scope_inflation(enriched: Dict[str, Any]) -> Dict[str, Any] | None:
    """Detect scope inflation — selected examples treated as universal description.

    Fires when: high-centrality claims with limited evidence exist alongside
    omission dependence signals (missing alternative perspectives). This
    combination suggests the article generalizes from narrow evidence while
    excluding the broader context that would limit those generalizations.
    """
    claims = _sl(enriched.get("adjudicated_claims"))
    lb = _sd(enriched.get("load_bearing"))
    ranked = _sl(enriched.get("ranked_omissions"))

    # Need high-centrality claims with weak evidence support
    thin_evidence_central = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        centrality = c.get("centrality", 1)
        if not isinstance(centrality, int) or centrality < 2:
            continue
        eids = c.get("evidence_eids", [])
        if not isinstance(eids, list):
            eids = []
        adj = c.get("adjudication", "")
        # Central claim with thin evidence (0-1 sources) that was kept
        if len(eids) <= 1 and adj == "kept":
            thin_evidence_central.append(c)

    if len(thin_evidence_central) < 2:
        return None

    # Also need omission signals (alternative perspectives missing)
    significant_omissions = [
        om for om in ranked
        if isinstance(om, dict) and om.get("severity") in ("load_bearing", "important")
    ]
    if not significant_omissions:
        return None

    body_parts = [
        f"The article makes {len(thin_evidence_central)} central claim(s) "
        f"supported by thin evidence (0-1 sources each), while "
        f"{len(significant_omissions)} significant perspective(s) are absent."
    ]
    body_parts.append(
        "This combination — broad claims with narrow evidence, "
        "plus missing alternative viewpoints — means selected examples "
        "are being treated as a complete description."
    )
    for c in thin_evidence_central[:3]:
        text = _trunc(c.get("text", ""), 100)
        if text:
            body_parts.append(f"- \"{text}\"")
    body_parts.append(
        "\nWhen a few examples stand in for an entire phenomenon, "
        "you stop evaluating evidence and start accepting a story."
    )

    return {
        "mechanism": "scope_inflation",
        "title": "It takes selected examples and treats them as the whole picture",
        "body": "\n".join(body_parts),
        "source_signals": [
            {"type": "thin_evidence_central_claims", "count": len(thin_evidence_central)},
            {"type": "significant_omissions", "count": len(significant_omissions)},
        ],
    }


# ---------------------------------------------------------------------------
# Bottom line synthesis
# ---------------------------------------------------------------------------

def _synthesize_bottom_line(
    enriched: Dict[str, Any],
    blocks: List[Dict[str, Any]],
) -> str:
    """Build a plain-language bottom line from classification + mechanism blocks."""
    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))
    classification = _s(waj.get("classification")) or "not assessed"

    claims = _sl(enriched.get("adjudicated_claims"))
    total = len([c for c in claims if isinstance(c, dict)])
    supported = sum(
        1 for c in claims
        if isinstance(c, dict) and c.get("adjudication") == "kept"
    )

    lb = _sd(enriched.get("load_bearing"))
    fragility = _s(lb.get("argument_fragility"))

    # Build assessment
    parts = []

    # Classification sentence — context-aware
    mechanism_names = [b["mechanism"] for b in blocks]
    is_propaganda_pattern = (
        len(blocks) >= 3
        or ("omission_dependence" in mechanism_names and "load_bearing_weakness" in mechanism_names)
    )

    if is_propaganda_pattern and classification.lower() in (
        "advocacy", "propaganda", "propaganda_patterned_advocacy", "mobilizing",
    ):
        parts.append(
            f"This article is best read as **propaganda-patterned {classification}**, "
            f"not as balanced analysis."
        )
    else:
        parts.append(f"This article is best read as **{classification}**.")

    # Support ratio
    if total > 0:
        rejected = sum(
            1 for c in claims
            if isinstance(c, dict) and c.get("adjudication") == "rejected"
        )
        if rejected > 0:
            parts.append(
                f"{supported} of {total} core claims are supported; "
                f"{rejected} were rejected by the review process."
            )
        else:
            parts.append(f"{supported} of {total} core claims are supported.")

    # Mechanism summary — what the structure does (richer combinations)
    if "scope_inflation" in mechanism_names:
        parts.append(
            "The argument expands selected examples into universal descriptions."
        )

    if "omission_dependence" in mechanism_names and "load_bearing_weakness" in mechanism_names:
        parts.append(
            "It depends on excluding alternative explanations "
            "and places its strongest conclusions on its weakest evidence."
        )
    elif "omission_dependence" in mechanism_names:
        parts.append(
            "The argument depends on excluding alternative explanations "
            "to maintain its coherence."
        )
    elif "load_bearing_weakness" in mechanism_names:
        parts.append(
            "The most important conclusions rest on "
            "the least well-supported claims."
        )

    if "unsupported_causal" in mechanism_names:
        parts.append(
            "Key causal claims are asserted rather than demonstrated."
        )

    if "framing_escalation" in mechanism_names:
        parts.append(
            "The framing escalates beyond what the evidence supports."
        )

    # Fragility
    if fragility == "high":
        parts.append("The argument is structurally fragile.")
    elif fragility == "elevated":
        parts.append("The argument has notable structural weaknesses.")

    # Reader guidance based on pattern severity — the "human voice"
    if len(blocks) >= 3:
        parts.append(
            "If you feel pulled more than shown, "
            "certain more than demonstrated, "
            "and alarmed before being given real comparative evidence — "
            "that is not an accident. That is the structure working."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpret_for_reader(
    enriched: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce reader-facing interpretation from enriched substrate.

    Returns:
        {
            "mechanism_blocks": [...],   # ordered list of mechanism dicts
            "bottom_line_plain": str,    # synthesized bottom line
            "block_count": int,          # how many mechanisms fired
        }

    Each mechanism block:
        {
            "mechanism": str,            # machine-readable type
            "title": str,                # reader-facing heading
            "body": str,                 # plain-language explanation
            "source_signals": [...]      # traceability
        }
    """
    if not isinstance(enriched, dict):
        return {
            "mechanism_blocks": [],
            "bottom_line_plain": "Not assessed.",
            "block_count": 0,
        }

    # Run all detectors in priority order
    _DETECTORS = [
        _detect_scope_inflation,
        _detect_omission_dependence,
        _detect_unsupported_causal,
        _detect_framing_escalation,
        _detect_load_bearing_weakness,
        _detect_official_reliance,
        _detect_baseline_absence,
    ]

    blocks: List[Dict[str, Any]] = []
    for detector in _DETECTORS:
        try:
            result = detector(enriched)
            if result is not None:
                blocks.append(result)
        except Exception:
            continue  # fail-closed per detector

    bottom_line = _synthesize_bottom_line(enriched, blocks)

    return {
        "mechanism_blocks": blocks,
        "bottom_line_plain": bottom_line,
        "block_count": len(blocks),
    }
