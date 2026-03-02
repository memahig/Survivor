#!/usr/bin/env python3
"""
FILE: engine/render/blunt_biaslens.py
VERSION: 0.1
PURPOSE:
Render a narrative "Blunt Report" from Survivor run_state.

DOCTRINE:
- No stars, no ratings, no caps, no bullet telemetry.
- Headers + narrative paragraphs only.
- Strictly structure-grounded: no intent or motive inference.
- Fail-closed: if a module is absent, say "not assessed" explicitly.
- No moral framing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _sd(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _sl(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _first_gsae_subject(phase2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for name in sorted(phase2.keys()):
        pack = _sd(phase2.get(name))
        subj = pack.get("gsae_subject")
        if isinstance(subj, dict):
            return subj
    return None


def _disagreement_score(tally: Dict[str, Any]) -> int:
    if not isinstance(tally, dict):
        return 0
    s = int(tally.get("supported_votes", 0) or 0)
    u = int(tally.get("unsupported_votes", 0) or 0)
    d = int(tally.get("undetermined_votes", 0) or 0)
    return (min(s, u) * 3) + d


def render_blunt_biaslens(run_state: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Render a narrative Blunt Report from Survivor run_state."""
    article = _sd(run_state.get("article"))
    adjudicated = _sd(run_state.get("adjudicated"))
    phase2 = _sd(run_state.get("phase2"))

    lines: List[str] = []

    # ---- Header ----
    title = article.get("title", "(untitled)")
    source = article.get("source_url", "")
    lines.append(f"# The Blunt Report\n")
    if title != "(untitled)":
        lines.append(f"**Article:** {title}\n")
    if source:
        lines.append(f"**Source:** {source}\n")
    lines.append("\n---\n")

    # ---- Section 1: What the article argues ----
    lines.append("## What the article argues\n")
    adjud_waj = _sd(_sd(adjudicated.get("article_track")).get("adjudicated_whole_article_judgment"))
    classification = adjud_waj.get("classification", "(not assessed)")
    confidence = adjud_waj.get("confidence", "(not assessed)")

    lines.append(
        f"The adjudicated classification for this article is **{classification}** "
        f"with **{confidence}** confidence across reviewers.\n\n"
    )

    # Show dominant reviewer judgments in narrative form
    reviewer_judgments = []
    for model in sorted(phase2.keys()):
        pack = _sd(phase2.get(model))
        waj = _sd(pack.get("whole_article_judgment"))
        cls = waj.get("classification", None)
        conf = waj.get("confidence", None)
        if cls:
            reviewer_judgments.append(f"{model} classified it as {cls} ({conf} confidence)")

    if reviewer_judgments:
        lines.append("Individual reviewers: " + "; ".join(reviewer_judgments) + ".\n")

    lines.append("\n---\n")

    # ---- Section 2: What survives review ----
    lines.append("## What survives review\n")
    arena = _sd(_sd(adjudicated.get("claim_track")).get("arena"))
    adj_claims = _sl(arena.get("adjudicated_claims"))

    supported = [_sd(c) for c in adj_claims if _sd(c).get("adjudication") == "supported"]
    unsupported = [_sd(c) for c in adj_claims if _sd(c).get("adjudication") == "unsupported"]
    undetermined = [_sd(c) for c in adj_claims if _sd(c).get("adjudication") == "undetermined"]

    total = len(adj_claims)
    if total == 0:
        lines.append("No claims were extracted or adjudicated for this article.\n")
    else:
        lines.append(
            f"Of {total} claim groups adjudicated, "
            f"{len(supported)} were supported, "
            f"{len(unsupported)} were unsupported, "
            f"and {len(undetermined)} remained undetermined.\n\n"
        )

        if supported:
            lines.append("**Supported claims:**\n\n")
            for c in supported[:10]:
                text = (c.get("text") or "(no text)").strip()
                lines.append(f"- {text}\n")
            if len(supported) > 10:
                lines.append(f"\n({len(supported) - 10} additional supported claims not shown.)\n")
            lines.append("\n")

        if unsupported:
            lines.append("**Claims that did not survive review:**\n\n")
            for c in unsupported[:10]:
                text = (c.get("text") or "(no text)").strip()
                lines.append(f"- {text}\n")
            if len(unsupported) > 10:
                lines.append(f"\n({len(unsupported) - 10} additional unsupported claims not shown.)\n")
            lines.append("\n")

    lines.append("\n---\n")

    # ---- Section 3: Where reviewers disagreed ----
    lines.append("## Where reviewers disagreed\n")

    if not adj_claims:
        lines.append("No adjudicated claims available for disagreement analysis.\n")
    else:
        scored = []
        for c in adj_claims:
            c = _sd(c)
            score = _disagreement_score(_sd(c.get("tally")))
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])

        if not scored:
            lines.append("Reviewers were broadly in agreement on all adjudicated claims.\n")
        else:
            lines.append(
                f"Reviewers diverged on {len(scored)} claim group(s). "
                "The following had the strongest disagreement:\n\n"
            )
            for score, c in scored[:5]:
                text = (c.get("text") or "(no text)").strip()
                adj = c.get("adjudication", "undetermined")
                lines.append(f"- **{adj}:** {text}\n")

            if len(scored) > 5:
                lines.append(f"\n({len(scored) - 5} additional disagreement zones not shown.)\n")

    lines.append("\n---\n")

    # ---- Section 4: Symmetry analysis ----
    lines.append("## Symmetry analysis\n")
    gsae = run_state.get("gsae")

    if not isinstance(gsae, dict):
        lines.append("Symmetry analysis was not performed for this article.\n")
    else:
        settings = _sd(gsae.get("settings"))
        artifacts = _sl(gsae.get("artifacts"))

        # Determine obs reviewers in sorted order
        obs_reviewers = []
        for name in sorted(phase2.keys()):
            pack = _sd(phase2.get(name))
            if "gsae_observation" in pack:
                obs_reviewers.append(name)
        obs_index = {name: i for i, name in enumerate(obs_reviewers)}

        subj = _first_gsae_subject(phase2)
        if subj:
            s_label = subj.get("subject_label", "(unknown)")
            c_label = subj.get("counterparty_label", "(unknown)")
            lines.append(
                f"The symmetry engine evaluated directional severity between "
                f"**{s_label}** and **{c_label}**.\n\n"
            )

        quarantined = []
        passed = []
        flagged = []

        for reviewer in sorted(phase2.keys()):
            idx = obs_index.get(reviewer)
            if idx is None or idx >= len(artifacts):
                continue
            art = _sd(artifacts[idx])
            status = art.get("symmetry_status", "UNKNOWN")
            if status == "QUARANTINE":
                quarantined.append(reviewer)
            elif status == "SOFT_FLAG":
                flagged.append(reviewer)
            else:
                passed.append(reviewer)

        if passed:
            lines.append(
                f"Reviewers that passed the symmetry check: {', '.join(passed)}.\n\n"
            )
        if flagged:
            lines.append(
                f"Reviewers with a soft flag (minor asymmetry detected): {', '.join(flagged)}.\n\n"
            )
        if quarantined:
            lines.append(
                f"Reviewers quarantined for structural asymmetry: {', '.join(quarantined)}. "
                "Their symmetry observations were removed before adjudication to prevent "
                "directional severity drift from influencing the final judgment.\n\n"
            )
        if not passed and not flagged and not quarantined:
            lines.append("No reviewers had symmetry observations available for evaluation.\n")

    lines.append("\n---\n")

    # ---- Section 5: Omissions ----
    lines.append("## Omissions\n")

    has_omissions = False
    for model in sorted(phase2.keys()):
        pack = _sd(phase2.get(model))
        omissions = _sl(pack.get("omission_candidates"))
        if omissions:
            has_omissions = True
            break

    if not has_omissions:
        lines.append(
            "Omission analysis was not assessed for this article. "
            "This does not imply the absence of omissions.\n"
        )
    else:
        lines.append(
            "The following potential omissions were identified by reviewers. "
            "An omission is reported only as the absence of expected context, "
            "not as evidence of intent.\n\n"
        )
        for model in sorted(phase2.keys()):
            pack = _sd(phase2.get(model))
            omissions = _sl(pack.get("omission_candidates"))
            if not omissions:
                continue
            for om in omissions[:5]:
                om = _sd(om)
                text = (om.get("text") or om.get("description") or "(no description)").strip()
                lines.append(f"- {text}\n")

    lines.append("\n---\n")
    lines.append("*Generated by Survivor epistemic integrity pipeline.*\n")

    return "".join(lines)
