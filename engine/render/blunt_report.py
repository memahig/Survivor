#!/usr/bin/env python3
"""
FILE: engine/render/blunt_report.py
VERSION: 1.0
PURPOSE:
Reader-facing Blunt Report. 150-300 words target, hard max 400.
6 sections. Every sentence substrate-derived.

RULES:
- No hard-coded interpretive prose.
- No motive attribution.
- No euphemistic smoothing.
- Fail-closed: each section try/except → "Not assessed." on error.
- Reads enriched_substrate only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


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

def _section_what_it_appears_to_be(enriched: Dict[str, Any]) -> str:
    """What the object appears to be"""
    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))

    classification = _s(waj.get("classification")) or "not assessed"
    confidence = _s(waj.get("confidence")) or "not assessed"

    lines = [f"## What the object appears to be\n\n"]
    lines.append(
        f"This presents itself as **{classification}** "
        f"({confidence} confidence).\n"
    )

    # Check for reviewer split
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
            lines.append(f"Reviewers split: {'; '.join(parts)}.\n")

    return "".join(lines)


def _section_what_it_reads_like(enriched: Dict[str, Any]) -> str:
    """Section 2: What the object reads like. From reads_like_label module."""
    reads_like = _sd(enriched.get("reads_like"))
    label = _s(reads_like.get("label"))

    lines = ["\n## What the object reads like\n\n"]

    if label and "error" not in reads_like:
        lines.append(f"It reads like **{label}**.\n")
    else:
        lines.append("Not assessed.\n")
        return "".join(lines)

    # Add top 1-2 priority signals as supporting evidence
    signals = _sl(enriched.get("priority_signals"))
    shown = 0
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        summary = _s(sig.get("summary"))
        if summary and shown < 2:
            lines.append(f"- {summary}\n")
            shown += 1

    return "".join(lines)


def _section_story_in_brief(enriched: Dict[str, Any]) -> str:
    """The story in brief"""
    groups = _sl(enriched.get("adjudicated_claims"))

    lines = ["\n## The story in brief\n\n"]

    if not groups:
        lines.append("No claims were extracted.\n")
        return "".join(lines)

    # Filter to kept claims, sort by centrality desc
    kept = [
        _sd(g) for g in groups
        if isinstance(g, dict) and g.get("adjudication") == "kept"
    ]
    kept.sort(key=lambda g: -(g.get("centrality", 1) if isinstance(g.get("centrality"), int) else 1))

    # Prefer centrality >= 2, but include lower if < 3 results
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
    """Section 4: How the story is put together."""
    load_bearing = _sd(enriched.get("load_bearing"))

    lines = ["\n## How the story is put together\n\n"]

    if "error" in load_bearing:
        lines.append("Not assessed.\n")
        return "".join(lines)

    lb_ids = _sl(load_bearing.get("load_bearing_group_ids"))
    wl_ids = _sl(load_bearing.get("weak_link_group_ids"))
    fragility = _s(load_bearing.get("argument_fragility")) or "unknown"

    n_lb = len(lb_ids)
    n_wl = len(wl_ids)

    if n_lb > 0:
        lines.append(
            f"{n_lb} claim(s) carry the argument's weight. "
            f"Argument fragility: **{fragility}**.\n"
        )
    else:
        lines.append(
            f"No load-bearing claims identified. "
            f"Argument fragility: **{fragility}**.\n"
        )

    if n_wl > 0:
        lines.append(f"{n_wl} of these are structurally weak.\n")

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

    for om in significant[:3]:
        text = _truncate(_s(om.get("merged_text")), 100)
        severity = _s(om.get("severity"))
        if text:
            lines.append(f"- {text} [{severity}]\n")

    return "".join(lines)


def _section_bottom_line(enriched: Dict[str, Any]) -> str:
    """Bottom line"""
    waj = _sd(enriched.get("adjudicated_whole_article_judgment"))
    classification = _s(waj.get("classification")) or "not assessed"

    groups = _sl(enriched.get("adjudicated_claims"))

    lines = ["\n## Bottom line\n\n"]

    # Support stats — use adjudication status, not vote arithmetic
    total = len([g for g in groups if isinstance(g, dict)])
    supported = sum(
        1 for g in groups
        if isinstance(g, dict) and g.get("adjudication") == "kept"
    )

    # Fragility
    load_bearing = _sd(enriched.get("load_bearing"))
    fragility = _s(load_bearing.get("argument_fragility"))

    fragility_desc = ""
    if fragility == "high":
        fragility_desc = "The argument is structurally fragile."
    elif fragility == "elevated":
        fragility_desc = "The argument has notable structural weaknesses."
    elif fragility == "low":
        fragility_desc = "The argument is structurally stable."

    # Top signal
    signals = _sl(enriched.get("priority_signals"))
    top_signal = ""
    if signals and isinstance(signals[0], dict):
        top_signal = _s(signals[0].get("summary"))

    parts = [f"**{classification.title()}.**"]
    if total > 0:
        parts.append(f"{supported} of {total} core claims supported.")
    if fragility_desc:
        parts.append(fragility_desc)
    if top_signal:
        parts.append(top_signal + ".")

    lines.append(" ".join(parts) + "\n")

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


def _enforce_word_limit(sections: List[str], max_words: int = 300) -> List[str]:
    """
    If total word count exceeds max_words, trim sections 3 and 5 first.
    Sections are 0-indexed: section 3 is index 2, section 5 is index 4.
    """
    total = sum(_word_count(s) for s in sections)
    if total <= max_words:
        return sections

    # Trim section 5 (index 4) bullets down to 2, then 1
    for keep in (2, 1):
        if len(sections) > 4:
            sections[4] = _trim_bullets(sections[4], keep)
        total = sum(_word_count(s) for s in sections)
        if total <= max_words:
            return sections

    # Trim section 3 (index 2) bullets down to 3, then 2
    for keep in (3, 2):
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

    6 sections, 150-300 words target.
    Every sentence substrate-derived.
    Fail-closed per section.
    """
    if config is None:
        config = {}

    sections: List[str] = []

    _SECTION_RENDERERS = [
        ("What the object appears to be", _section_what_it_appears_to_be),
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
    max_words = config.get("blunt_max_words", 300)
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

    reads_like = _sd(enriched.get("reads_like"))
    load_bearing = _sd(enriched.get("load_bearing"))
    signals = _sl(enriched.get("priority_signals"))
    ranked_omissions = _sl(enriched.get("ranked_omissions"))

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
    ][:3]

    return {
        "what_it_appears_to_be": {
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
        },
        "how_put_together": {
            "load_bearing_count": len(_sl(load_bearing.get("load_bearing_group_ids"))),
            "weak_link_count": len(_sl(load_bearing.get("weak_link_group_ids"))),
            "fragility": _s(load_bearing.get("argument_fragility")),
        },
        "whats_missing": {
            "omissions": sig_omissions,
        },
        "bottom_line": {
            "classification": _s(waj.get("classification")),
            "supported_count": supported,
            "total_count": len(groups),
            "fragility": _s(load_bearing.get("argument_fragility")),
            "top_signal": _s(signals[0].get("summary")) if signals and isinstance(signals[0], dict) else "",
        },
    }
