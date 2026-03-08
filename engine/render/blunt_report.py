#!/usr/bin/env python3
"""
FILE: engine/render/blunt_report.py
VERSION: 2.1
PURPOSE:
Reader-facing Blunt Report. Forensic storytelling — explains HOW the
article's argument works on the reader, not just structural counts.

AUTHORITY ORDER:
- PEG profile drives Section 1 (opening) and Section 6 (bottom line)
  when PEG level is severe or critical.
- Old reviewer classification is secondary context, not the controlling label.

RULES:
- No hard-coded interpretive prose.
- No motive attribution.
- No euphemistic smoothing.
- Fail-closed: each section try/except -> "Not assessed." on error.
- Reads enriched_substrate only.
- Every sentence substrate-derived.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---- BLUNT STRUCTURAL WARNING FORMAT ----
#
# The renderer should follow this pattern when PEG is critical:
#
# 1. Structural label
# 2. Mechanism explanation
# 3. Reader impact
#
# Example:
#
# This article has the structure of propaganda.
#
# The argument depends on omitted rival explanations, unsupported causal claims,
# and escalating existential framing.
#
# These mechanisms push the reader toward a conclusion before the evidence
# fully supports it.
#
# Do NOT soften structural labels with phrases such as:
# "appears to", "may be", "could be considered".
#
# The system explains mechanisms rather than speculating about author intent.


# ---- Safe accessors ----

def _sd(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _sl(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _s(x: Any) -> str:
    return str(x or "").strip()


def _truncate(s: str, n: int) -> str:
    s = _s(s)
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "\u2026"


def _word_count(text: str) -> int:
    return len(text.split())


# ---- Section renderers ----

def _section_what_it_is(enriched: Dict[str, Any]) -> str:
    """Section 1: What the object is — PEG-driven structural label when
    severe/critical, old classification as fallback. No hedging."""
    peg = _sd(enriched.get("peg_profile"))
    peg_level = _s(peg.get("peg_level"))
    peg_line = _s(peg.get("peg_line"))

    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))
    classification = _s(waj.get("classification")) or "not assessed"

    lines = ["## What the object is\n\n"]

    # PEG-driven opening when severe or critical — no hedging
    if peg_level in ("severe", "critical") and peg_line:
        lines.append(f"**{peg_line}**\n\n")
    else:
        lines.append(f"This is **{classification}**.\n")

    # Reviewer split as secondary context
    phase2 = _sd(enriched.get("phase2"))
    if phase2:
        classifications: Dict[str, List[str]] = {}
        for name in sorted(phase2.keys()):
            pack = _sd(phase2.get(name))
            r_waj = _sd(pack.get("whole_article_judgment"))
            cls = _s(r_waj.get("classification"))
            if cls:
                classifications.setdefault(cls.lower(), []).append(name.title())

        if len(classifications) > 1:
            parts = []
            for cls_val, names in sorted(classifications.items(), key=lambda x: -len(x[1])):
                parts.append(f"{' and '.join(names)}: {cls_val}")
            lines.append(f"Reviewer classification: {'; '.join(parts)}.\n")

    return "".join(lines)


def _section_what_it_reads_like(enriched: Dict[str, Any]) -> str:
    """Section 2: What the object reads like — reads_like label + load-bearing signals."""
    reads_like = _sd(enriched.get("reads_like"))
    label = _s(reads_like.get("label"))

    lines = ["\n## What the object reads like\n\n"]

    if label and "error" not in reads_like:
        lines.append(f"It reads like **{label}**.\n")
    else:
        lines.append("Not assessed.\n")
        return "".join(lines)

    # Show top load-bearing failures as concrete evidence for the reads-like label
    interp = _sd(enriched.get("reader_interpretation"))
    blocks = _sl(interp.get("mechanism_blocks"))
    if blocks and "error" not in interp:
        lb_block = next(
            (b for b in blocks if isinstance(b, dict) and b.get("mechanism") == "load_bearing_weakness"),
            None,
        )
        if lb_block:
            # Extract the rejected/downgraded claims from load-bearing
            lb_data = _sd(enriched.get("load_bearing"))
            claims = _sl(enriched.get("adjudicated_claims"))
            lb_ids = set(_sl(lb_data.get("load_bearing_group_ids")))
            for c in claims:
                if not isinstance(c, dict):
                    continue
                gid = c.get("group_id", "")
                adj = c.get("adjudication", "")
                if gid in lb_ids and adj in ("rejected", "downgraded"):
                    text = _truncate(_s(c.get("text")), 120)
                    if text:
                        lines.append(f"\nLoad-bearing claim {adj}: \"{text}\"\n")

    return "".join(lines)


def _section_story_in_brief(enriched: Dict[str, Any]) -> str:
    """Section 3: The story in brief — uses story clusters when available,
    falls back to high-centrality kept claims."""
    clusters = _sl(enriched.get("story_clusters"))
    groups = _sl(enriched.get("adjudicated_claims"))

    lines = ["\n## The story in brief\n\n"]

    # Prefer story clusters (grouped by topic)
    if clusters and not isinstance(enriched.get("story_clusters"), dict):
        # Filter to clusters with at least one kept claim, sort by max_centrality
        kept_clusters = []
        for cl in clusters:
            if not isinstance(cl, dict):
                continue
            adj_summary = _sd(cl.get("adjudication_summary"))
            if adj_summary.get("kept", 0) > 0:
                kept_clusters.append(cl)

        kept_clusters.sort(
            key=lambda c: -(c.get("max_centrality", 1) if isinstance(c.get("max_centrality"), int) else 1)
        )

        if kept_clusters:
            lines.append("The article's core arguments:\n\n")
            for cl in kept_clusters[:5]:
                text = _truncate(_s(cl.get("canonical_text")), 120)
                member_count = len(_sl(cl.get("member_group_ids")))
                if text:
                    if member_count > 1:
                        lines.append(f"- {text} ({member_count} related claims)\n")
                    else:
                        lines.append(f"- {text}\n")
            return "".join(lines)

    # Fallback: kept claims sorted by centrality
    if not groups:
        lines.append("No claims were extracted.\n")
        return "".join(lines)

    kept = [
        _sd(g) for g in groups
        if isinstance(g, dict) and g.get("adjudication") == "kept"
    ]
    kept.sort(key=lambda g: -(g.get("centrality", 1) if isinstance(g.get("centrality"), int) else 1))

    high = [g for g in kept if isinstance(g.get("centrality"), int) and g.get("centrality", 0) >= 2]
    if len(high) < 3:
        high = kept

    shown = high[:5]
    if not shown:
        lines.append("No supported claims available.\n")
        return "".join(lines)

    lines.append("The article's core claims:\n\n")
    for g in shown:
        text = _truncate(_s(g.get("text")), 120)
        if text:
            lines.append(f"- {text}\n")

    return "".join(lines)


def _section_how_put_together(enriched: Dict[str, Any]) -> str:
    """Section 4: How the story is put together — numbered mechanism blocks
    from the interpretation layer. This is the forensic storytelling section."""
    interp = _sd(enriched.get("reader_interpretation"))
    blocks = _sl(interp.get("mechanism_blocks"))

    lines = ["\n## How the story is put together\n\n"]

    if not blocks or "error" in interp:
        # Fallback to structural summary
        load_bearing = _sd(enriched.get("load_bearing"))
        if "error" in load_bearing:
            lines.append("Not assessed.\n")
            return "".join(lines)
        lb_ids = _sl(load_bearing.get("load_bearing_group_ids"))
        fragility = _s(load_bearing.get("argument_fragility")) or "unknown"
        if lb_ids:
            lines.append(
                f"{len(lb_ids)} claim(s) carry the argument's weight. "
                f"Argument fragility: **{fragility}**.\n"
            )
        else:
            lines.append("No structural mechanisms detected.\n")
        return "".join(lines)

    # Render numbered mechanism blocks
    block_num = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        title = _s(block.get("title"))
        body = _s(block.get("body"))
        if not title:
            continue
        block_num += 1
        lines.append(f"### {block_num}. {title}\n\n")
        if body:
            lines.append(f"{body}\n\n")

    return "".join(lines)


def _section_whats_missing(enriched: Dict[str, Any]) -> str:
    """Section 5: What's missing. Load-bearing and important omissions only."""
    ranked = _sl(enriched.get("ranked_omissions"))

    lines = ["\n## What's missing\n\n"]

    if not ranked or (isinstance(enriched.get("ranked_omissions"), dict)):
        lines.append("Not assessed.\n")
        return "".join(lines)

    # Filter to load_bearing and important
    significant = [
        om for om in ranked
        if isinstance(om, dict) and om.get("severity") in ("load_bearing", "important")
    ]

    if not significant:
        lines.append("No significant omissions identified.\n")
        return "".join(lines)

    shown = 0
    max_show = 5

    for om in significant:
        if shown >= max_show:
            break
        text = _truncate(_s(om.get("merged_text")), 140)
        if not text:
            continue
        kind = om.get("kind", "")
        frame_used = _truncate(_s(om.get("frame_used_by_article")), 80)
        if kind == "framing_omission" and frame_used:
            lines.append(f"- Frame used: \"{frame_used}\" \u2014 missing: \"{text}\"\n")
        else:
            lines.append(f"- {text}\n")
        shown += 1

    remaining = len(significant) - shown
    if remaining > 0:
        lines.append(f"\n({remaining} additional omission(s) not shown.)\n")

    return "".join(lines)


def _render_esm_line(enriched: Dict[str, Any]) -> str:
    """Render epistemic quality line from ESM profile, if notable or above."""
    esm = _sd(enriched.get("esm_profile"))
    level = _s(esm.get("success_level"))
    line = _s(esm.get("integrity_line"))
    if level in ("notable", "high", "exceptional") and line:
        return f"\n**Epistemic quality:** {line}\n"
    return ""


def _section_bottom_line(enriched: Dict[str, Any]) -> str:
    """Section 6: Bottom line — PEG-driven when severe/critical,
    falls back to reader_interpretation.bottom_line_plain, then structural summary.
    ESM epistemic quality line appended when notable or above."""
    lines = ["\n## Bottom line\n\n"]

    # PEG authority: when PEG is severe or critical, PEG gets the last word
    peg = _sd(enriched.get("peg_profile"))
    peg_level = _s(peg.get("peg_level"))
    peg_line = _s(peg.get("peg_line"))

    if peg_level in ("severe", "critical") and peg_line:
        lines.append(f"{peg_line}\n")
        lines.append(_render_esm_line(enriched))
        return "".join(lines)

    # Fallback: reader_interpretation bottom line (for notable/minimal)
    interp = _sd(enriched.get("reader_interpretation"))
    bottom = _s(interp.get("bottom_line_plain"))

    if bottom and "error" not in interp:
        lines.append(f"{bottom}\n")
        lines.append(_render_esm_line(enriched))
        return "".join(lines)

    # Final fallback: structural summary
    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))
    classification = _s(waj.get("classification")) or "not assessed"
    groups = _sl(enriched.get("adjudicated_claims"))
    total = len([g for g in groups if isinstance(g, dict)])
    supported = sum(
        1 for g in groups
        if isinstance(g, dict) and g.get("adjudication") == "kept"
    )

    lb = _sd(enriched.get("load_bearing"))
    fragility = _s(lb.get("argument_fragility"))

    parts = [f"**{classification.title()}.**"]
    if total > 0:
        parts.append(f"{supported} of {total} core claims supported.")
    if fragility in ("high", "elevated"):
        parts.append(f"The argument is structurally {fragility}.")
    lines.append(" ".join(parts) + "\n")
    lines.append(_render_esm_line(enriched))

    return "".join(lines)


# ---- Word count enforcement ----

def _trim_bullets(section: str, keep: int) -> str:
    """Reduce bullet lines (starting with '- ') to at most `keep`."""
    lines = section.split("\n")
    bullets = [i for i, ln in enumerate(lines) if ln.startswith("- ")]
    if len(bullets) <= keep:
        return section
    remove = set(bullets[keep:])
    return "\n".join(ln for i, ln in enumerate(lines) if i not in remove)


def _enforce_word_limit(sections: List[str], max_words: int = 1500) -> List[str]:
    """
    If total word count exceeds max_words, trim section 3 (story in brief) only.
    Never trim section 5 (omissions) — that is critical forensic content.
    Sections are 0-indexed: section 3 is index 2.
    """
    total = sum(_word_count(s) for s in sections)
    if total <= max_words:
        return sections

    # Trim section 3 (index 2) bullets down to 4, then 3
    for keep in (4, 3):
        if len(sections) > 2:
            sections[2] = _trim_bullets(sections[2], keep)
        total = sum(_word_count(s) for s in sections)
        if total <= max_words:
            return sections

    return sections


# ---- Public API ----

def render_blunt_report(
    enriched: Dict[str, Any],
    config: Dict[str, Any] | None = None,
) -> str:
    """
    Render the reader-facing Blunt Report from enriched substrate.

    6 sections, forensic storytelling structure.
    PEG drives opening and bottom line when severe/critical.
    Every sentence substrate-derived.
    Fail-closed per section.
    """
    if config is None:
        config = {}

    sections: List[str] = []

    _SECTION_RENDERERS = [
        ("What the object is", _section_what_it_is),
        ("What the object reads like", _section_what_it_reads_like),
        ("The story in brief", _section_story_in_brief),
        ("How the story is put together", _section_how_put_together),
        ("What's missing", _section_whats_missing),
        ("Bottom line", _section_bottom_line),
    ]

    for title, renderer in _SECTION_RENDERERS:
        try:
            sections.append(renderer(enriched))
        except Exception:
            sections.append(f"\n## {title}\n\nNot assessed.\n")

    # Word count enforcement
    max_words = config.get("blunt_max_words", 1500)
    sections = _enforce_word_limit(sections, max_words)

    # Header
    article = _sd(enriched.get("article"))
    title = _s(article.get("title")) or "(untitled)"

    header = f"# The Blunt Report\n\n**Article:** {title}\n\n---\n"
    footer = "\n---\n\n*Generated by Survivor (multi-reviewer, evidence-indexed).*\n"

    body = "\n".join(sections)
    return header + body + footer


def render_blunt_report_json(
    enriched: Dict[str, Any],
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Structured JSON representation of the Blunt Report.
    """
    if config is None:
        config = {}

    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))
    groups = _sl(enriched.get("adjudicated_claims"))
    peg = _sd(enriched.get("peg_profile"))

    reads_like = _sd(enriched.get("reads_like"))
    load_bearing = _sd(enriched.get("load_bearing"))
    signals = _sl(enriched.get("priority_signals"))
    ranked_omissions = _sl(enriched.get("ranked_omissions"))
    clusters = _sl(enriched.get("story_clusters"))

    # Support count — use adjudication status, not vote arithmetic
    supported = sum(
        1 for g in groups
        if isinstance(g, dict) and g.get("adjudication") == "kept"
    )

    # Top kept claims
    kept = sorted(
        [_sd(g) for g in groups if isinstance(g, dict) and g.get("adjudication") == "kept"],
        key=lambda g: -(g.get("centrality", 1) if isinstance(g.get("centrality"), int) else 1),
    )

    # Significant omissions
    sig_omissions = [
        {"text": _s(om.get("merged_text")), "severity": _s(om.get("severity"))}
        for om in ranked_omissions
        if isinstance(om, dict) and om.get("severity") in ("load_bearing", "important")
    ][:5]

    # Story clusters for JSON
    story_clusters_json = []
    for cl in clusters:
        if not isinstance(cl, dict):
            continue
        adj_summary = _sd(cl.get("adjudication_summary"))
        if adj_summary.get("kept", 0) > 0:
            story_clusters_json.append({
                "cluster_id": _s(cl.get("cluster_id")),
                "canonical_text": _truncate(_s(cl.get("canonical_text")), 120),
                "member_count": len(_sl(cl.get("member_group_ids"))),
                "max_centrality": cl.get("max_centrality", 1),
            })

    esm = _sd(enriched.get("esm_profile"))

    return {
        "peg_profile": peg,
        "epistemic_quality": {
            "level": _s(esm.get("success_level")),
            "summary": _s(esm.get("integrity_line")),
            "active_signals": _sl(esm.get("active_successes")),
            "domain_alignment": _s(esm.get("domain_alignment")),
        },
        "what_it_is": {
            "classification": _s(waj.get("classification")),
            "confidence": _s(waj.get("confidence")),
        },
        "what_it_reads_like": {
            "label": _s(reads_like.get("label")),
            "matched_rule": reads_like.get("matched_rule"),
            "flags": reads_like.get("flags", {}),
        },
        "story_in_brief": {
            "claims": [
                {
                    "text": _truncate(_s(g.get("text")), 120),
                    "adjudication": _s(g.get("adjudication")),
                    "centrality": g.get("centrality", 1),
                }
                for g in kept[:5]
            ],
            "story_clusters": story_clusters_json[:5],
        },
        "how_put_together": {
            "load_bearing_count": len(_sl(load_bearing.get("load_bearing_group_ids"))),
            "weak_link_count": len(_sl(load_bearing.get("weak_link_group_ids"))),
            "fragility": _s(load_bearing.get("argument_fragility")),
            "mechanism_blocks": _sl(_sd(enriched.get("reader_interpretation")).get("mechanism_blocks")),
        },
        "whats_missing": {
            "omissions": sig_omissions,
        },
        "bottom_line": {
            "peg_level": _s(peg.get("peg_level")),
            "peg_line": _s(peg.get("peg_line")),
            "classification": _s(waj.get("classification")),
            "supported_count": supported,
            "total_count": len(groups),
            "fragility": _s(load_bearing.get("argument_fragility")),
            "bottom_line_plain": _s(_sd(enriched.get("reader_interpretation")).get("bottom_line_plain")),
        },
    }
