#!/usr/bin/env python3
"""
FILE: engine/render/blunt_biaslens.py
VERSION: 0.2
PURPOSE:
Render a narrative "Blunt Report" from Survivor run_state.

REQUIREMENTS (LOCKED):
- Blunt-readable report suitable for humans.
- Must include:
  1) Extractive summary (no freeform summarization)
  2) Article type/classification
  3) "Lines that warrant comment" printed with an evaluation comment
  4) Bottom-line synthesis of what the findings amount to
- No stars/ratings.
- No motive/intent inference.
- Fail-closed for absent modules: say "not assessed" explicitly.
- Renderer must read run_state only and must not call models.

NOTE:
This renderer is *extractive*, not generative:
- Summary paragraphs are built from adjudicated claim-group texts + evidence quotes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Safe helpers
# -----------------------------
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


# -----------------------------
# Core mappings
# -----------------------------
def _disagreement_score(tally: Dict[str, Any]) -> int:
    if not isinstance(tally, dict):
        return 0
    s = int(tally.get("supported_votes", 0) or 0)
    u = int(tally.get("unsupported_votes", 0) or 0)
    d = int(tally.get("undetermined_votes", 0) or 0)
    return (min(s, u) * 3) + d


def _disagreement_descriptor(score: int) -> str:
    # Deterministic descriptor map (no raw telemetry exposed in prose)
    if score <= 0:
        return "total consensus"
    if 1 <= score <= 3:
        return "minor interpretive variance"
    if 4 <= score <= 6:
        return "moderate disagreement"
    return "high structural conflict"


def _adjudication_label(adj: str) -> str:
    adj = str(adj or "").strip().lower()
    if adj == "supported":
        return "Supported"
    if adj == "unsupported":
        return "Not supported"
    if adj == "undetermined":
        return "Undetermined"
    return adj.title() if adj else "Undetermined"


def _first_gsae_subject(phase2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for name in sorted(phase2.keys()):
        pack = _sd(phase2.get(name))
        subj = pack.get("gsae_subject")
        if isinstance(subj, dict):
            return subj
    return None


def _build_evidence_lookup(run_state: Dict[str, Any]) -> Dict[str, str]:
    """
    Build eid -> text map.
    Assumes Survivor run_state has evidence_bank.items = [{eid, text, ...}, ...]
    """
    out: Dict[str, str] = {}
    ev = _sd(run_state.get("evidence_bank"))
    for it in _sl(ev.get("items")):
        it = _sd(it)
        eid = _s(it.get("eid"))
        txt = _s(it.get("text"))
        if eid and txt:
            out[eid] = txt
    return out


def _build_claim_index(phase2: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build claim_id -> {centrality, type, reviewer} from phase2[*].claims.
    Used to approximate "centrality-first" without inventing anything.
    """
    idx: Dict[str, Dict[str, Any]] = {}
    for reviewer in sorted(phase2.keys()):
        pack = _sd(phase2.get(reviewer))
        for c in _sl(pack.get("claims")):
            c = _sd(c)
            cid = _s(c.get("claim_id"))
            if not cid:
                continue
            if cid not in idx:
                idx[cid] = {
                    "centrality": c.get("centrality"),
                    "type": c.get("type"),
                    "reviewer": reviewer,
                    "text": c.get("text"),
                }
    return idx


def _group_centrality(group: Dict[str, Any], claim_index: Dict[str, Dict[str, Any]]) -> int:
    """
    Best-effort centrality for a claim-group:
    max centrality among member claim IDs that exist in phase2 claim index.
    If missing everywhere, returns 0.
    """
    members = _sl(group.get("member_claim_ids"))
    best = 0
    for cid_any in members:
        cid = _s(cid_any)
        rec = claim_index.get(cid)
        if not rec:
            continue
        try:
            c = int(rec.get("centrality") or 0)
        except Exception:
            c = 0
        if c > best:
            best = c
    return best


def _group_primary_eid(group: Dict[str, Any], evidence_lookup: Dict[str, str]) -> Optional[str]:
    eids = _sl(group.get("evidence_eids"))
    for e in eids:
        eid = _s(e)
        if eid and eid in evidence_lookup:
            return eid
    # fallback: if evidence_eids exist but not found in lookup, return first non-empty
    for e in eids:
        eid = _s(e)
        if eid:
            return eid
    return None


def _group_sort_key(
    g: Dict[str, Any], claim_index: Dict[str, Dict[str, Any]]
) -> Tuple[int, int, str]:
    """Deterministic sort: centrality desc, disagreement desc, group_id asc."""
    return (
        -_group_centrality(g, claim_index),
        -_disagreement_score(_sd(g.get("tally"))),
        str(g.get("group_id", "")),
    )


# -----------------------------
# Public JSON output (optional)
# -----------------------------
def render_blunt_biaslens_json(run_state: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Structured JSON for the Blunt Report (optional UI output).
    This is a *render pack*, not the full run_state.
    """
    article = _sd(run_state.get("article"))
    adjudicated = _sd(run_state.get("adjudicated"))
    phase2 = _sd(run_state.get("phase2"))

    evidence_lookup = _build_evidence_lookup(run_state)
    claim_index = _build_claim_index(phase2)

    waj = _sd(_sd(adjudicated.get("article_track")).get("adjudicated_whole_article_judgment"))
    arena = _sd(_sd(adjudicated.get("claim_track")).get("arena"))
    groups = [_sd(g) for g in _sl(arena.get("adjudicated_claims"))]

    # Build commented lines list deterministically
    commented: List[Dict[str, Any]] = []
    for g in sorted(groups, key=lambda x: _group_sort_key(x, claim_index)):
        eid = _group_primary_eid(g, evidence_lookup)
        quote = evidence_lookup.get(eid, "") if eid else ""
        tally = _sd(g.get("tally"))
        score = _disagreement_score(tally)
        commented.append(
            {
                "group_id": g.get("group_id"),
                "adjudication": g.get("adjudication"),
                "label": _adjudication_label(g.get("adjudication")),
                "centrality": _group_centrality(g, claim_index),
                "disagreement_descriptor": _disagreement_descriptor(score),
                "evidence_eid": eid,
                "evidence_quote": quote,
                "claim_text": g.get("text"),
                "tally": tally,
                "reviewer_votes": g.get("reviewer_votes"),
            }
        )

    # Symmetry summary
    gsae = run_state.get("gsae")
    symmetry: Dict[str, Any] = {"status": "not_assessed"}
    if isinstance(gsae, dict):
        symmetry["status"] = "run"
        symmetry["settings"] = _sd(gsae.get("settings"))
        symmetry["artifacts_count"] = len(_sl(gsae.get("artifacts")))

    return {
        "article": {
            "id": article.get("id"),
            "title": article.get("title"),
            "source_url": article.get("source_url"),
        },
        "whole_article_judgment": {
            "classification": waj.get("classification"),
            "confidence": waj.get("confidence"),
            "evidence_eids": waj.get("evidence_eids", []),
        },
        "commented_lines": commented,
        "symmetry": symmetry,
        "modules": {
            "omissions": (
                "present_in_phase2_packets"
                if any(
                    _sl(_sd(phase2.get(m)).get("omission_candidates"))
                    for m in phase2
                )
                else "not_assessed"
            ),
            "verification": (
                "enabled"
                if bool(_sd(run_state.get("verification")).get("enabled", False))
                else "not_assessed"
            ),
        },
    }


# -----------------------------
# Markdown renderer
# -----------------------------
def render_blunt_biaslens(run_state: Dict[str, Any], config: Dict[str, Any]) -> str:
    """
    Narrative Blunt Report (Markdown), strictly run_state-derived.

    Key idea:
    - Extractive summary: built from high-centrality adjudicated claim-groups (no free summary).
    - Lines that warrant comment: print evidence quote + evaluation comment.
    """
    article = _sd(run_state.get("article"))
    adjudicated = _sd(run_state.get("adjudicated"))
    phase2 = _sd(run_state.get("phase2"))

    evidence_lookup = _build_evidence_lookup(run_state)
    claim_index = _build_claim_index(phase2)

    lines: List[str] = []

    # ---- Header ----
    title = article.get("title") or "(untitled)"
    source = article.get("source_url") or ""
    lines.append("# The Blunt Report\n")
    lines.append("**A new path, to understanding.**\n\n")
    lines.append(f"**Article:** {title}\n")
    if source:
        lines.append(f"**Source:** {source}\n")
    lines.append("\n---\n")

    # ---- Article type / classification ----
    waj = _sd(_sd(adjudicated.get("article_track")).get("adjudicated_whole_article_judgment"))
    classification = waj.get("classification", "not_assessed")
    confidence = waj.get("confidence", "not_assessed")

    lines.append("## What this is\n")
    lines.append(
        f"Survivor classifies this as **{classification}** "
        f"with **{confidence}** confidence across reviewers.\n"
    )

    reviewer_bits: List[str] = []
    for model in sorted(phase2.keys()):
        pack = _sd(phase2.get(model))
        r_waj = _sd(pack.get("whole_article_judgment"))
        cls = r_waj.get("classification")
        conf = r_waj.get("confidence")
        if cls:
            reviewer_bits.append(f"{model}: {cls} ({conf})")
    if reviewer_bits:
        lines.append("\nIndividual reviewers: " + "; ".join(reviewer_bits) + ".\n")

    lines.append("\n---\n")

    # ---- Claims / groups ----
    arena = _sd(_sd(adjudicated.get("claim_track")).get("arena"))
    groups = [_sd(g) for g in _sl(arena.get("adjudicated_claims"))]

    supported = [g for g in groups if str(g.get("adjudication")).lower() == "supported"]
    unsupported = [g for g in groups if str(g.get("adjudication")).lower() == "unsupported"]
    undetermined = [g for g in groups if str(g.get("adjudication")).lower() == "undetermined"]

    lines.append("## Extractive summary of what the article says\n")
    if not groups:
        lines.append("No claims were extracted or adjudicated for this article.\n")
        lines.append("\n---\n")
    else:
        ordered = sorted(groups, key=lambda g: _group_sort_key(g, claim_index))

        # Build a compact "spine" paragraph using the top central items (extractive).
        budget = int(config.get("summary_char_budget", 900))
        used = 0
        spine: List[str] = []
        for g in ordered:
            text = _truncate(_s(g.get("text") or ""), 220)
            if not text:
                continue
            piece = f"\u2022 {text}"
            if used + len(piece) + 1 > budget and spine:
                break
            spine.append(piece)
            used += len(piece) + 1

        if spine:
            lines.append("The core claims (as extracted and deduplicated across reviewers):\n\n")
            lines.append("\n".join(spine) + "\n")
        else:
            lines.append("Core claim spine could not be constructed (missing claim texts).\n")

        lines.append("\n\n---\n")

    # ---- Lines that warrant comment ----
    lines.append("## Lines that warrant comment\n")

    if not groups:
        lines.append("No adjudicated claim groups are available to annotate.\n")
    else:
        ordered = sorted(groups, key=lambda g: _group_sort_key(g, claim_index))

        for g in ordered:
            adj = _adjudication_label(g.get("adjudication"))
            tally = _sd(g.get("tally"))
            score = _disagreement_score(tally)
            conflict = _disagreement_descriptor(score)

            eid = _group_primary_eid(g, evidence_lookup)
            quote = evidence_lookup.get(eid, "") if eid else ""
            quote = _truncate(quote, int(config.get("quote_max_chars", 360)))

            claim_text = _truncate(_s(g.get("text") or ""), 260)

            # Comment is deterministic, structure-grounded
            comment_parts: List[str] = []
            comment_parts.append(f"**{adj}.**")
            comment_parts.append(f"Disagreement: **{conflict}**.")
            if eid:
                comment_parts.append(f"Anchor: `{eid}`.")
            else:
                comment_parts.append("Anchor: (no evidence EID available).")

            lines.append(f"**Claim:** {claim_text}\n\n")
            if quote:
                lines.append(f"> {quote}\n\n")
            lines.append("**Comment:** " + " ".join(comment_parts) + "\n")
            lines.append("\n---\n")

    # ---- Symmetry ----
    lines.append("## Symmetry analysis\n")
    gsae = run_state.get("gsae")
    if not isinstance(gsae, dict):
        lines.append("Status: **Not assessed** (module not executed in this run).\n")
    else:
        settings = _sd(gsae.get("settings"))
        artifacts = _sl(gsae.get("artifacts"))

        subj = _first_gsae_subject(phase2)
        if subj:
            s_label = subj.get("subject_label", "(unknown)")
            c_label = subj.get("counterparty_label", "(unknown)")
            lines.append(f"Subject vs counterparty: **{s_label}** vs **{c_label}**.\n\n")

        # Determine observation reviewers deterministically
        obs_reviewers: List[str] = []
        for name in sorted(phase2.keys()):
            pack = _sd(phase2.get(name))
            if "gsae_observation" in pack:
                obs_reviewers.append(name)
        obs_index = {name: i for i, name in enumerate(obs_reviewers)}

        passed: List[str] = []
        flagged: List[str] = []
        quarantined: List[str] = []

        for reviewer in sorted(phase2.keys()):
            idx = obs_index.get(reviewer)
            if idx is None or idx >= len(artifacts):
                continue
            art = _sd(artifacts[idx])
            status = str(art.get("symmetry_status", "UNKNOWN"))
            if status == "QUARANTINE":
                quarantined.append(reviewer)
            elif status == "SOFT_FLAG":
                flagged.append(reviewer)
            elif status == "PASS":
                passed.append(reviewer)

        if settings:
            ver = settings.get("version", "(missing)")
            eps = settings.get("epsilon", "(missing)")
            tau = settings.get("tau", "(missing)")
            lines.append(f"Settings: version={ver}, epsilon={eps}, tau={tau}.\n\n")

        if passed:
            lines.append("Passed: " + ", ".join(passed) + ".\n")
        if flagged:
            lines.append("Soft-flagged: " + ", ".join(flagged) + ".\n")
        if quarantined:
            lines.append(
                "Quarantined: " + ", ".join(quarantined) + ". "
                "Affected symmetry observations were removed before adjudication to prevent "
                "directional framing asymmetry from influencing the consensus layer.\n"
            )
        if not (passed or flagged or quarantined):
            lines.append("No symmetry observations were available for evaluation.\n")

    lines.append("\n---\n")

    # ---- Omissions ----
    lines.append("## Omissions\n")
    has_om = any(_sl(_sd(phase2.get(m)).get("omission_candidates")) for m in phase2)
    if not has_om:
        lines.append("Status: **Not assessed** (no omission module output present in this run).\n")
        lines.append("This does not imply the absence of omissions.\n")
    else:
        lines.append(
            "Potential omissions reported by reviewers "
            "(treated only as absence of expected context; not intent):\n\n"
        )
        for model in sorted(phase2.keys()):
            pack = _sd(phase2.get(model))
            omits = _sl(pack.get("omission_candidates"))
            if not omits:
                continue
            lines.append(f"**{model}:**\n")
            for om in omits:
                om = _sd(om)
                txt = _s(om.get("text") or om.get("description") or "")
                if txt:
                    lines.append(f"- {txt}\n")
            lines.append("\n")

    lines.append("\n---\n")

    # ---- Bottom line ----
    lines.append("## Bottom line\n")
    if not groups:
        lines.append(
            "No adjudicated claims means Survivor could not recover "
            "a stable claim structure from this run.\n"
        )
    else:
        lines.append(
            f"Recovered claim structure: {len(groups)} adjudicated claim group(s) "
            f"({len(supported)} supported, {len(unsupported)} not supported, "
            f"{len(undetermined)} undetermined).\n"
        )
        conflict_counts = {"total_consensus": 0, "minor": 0, "moderate": 0, "high": 0}
        for g in groups:
            score = _disagreement_score(_sd(g.get("tally")))
            desc = _disagreement_descriptor(score)
            if desc == "total consensus":
                conflict_counts["total_consensus"] += 1
            elif desc == "minor interpretive variance":
                conflict_counts["minor"] += 1
            elif desc == "moderate disagreement":
                conflict_counts["moderate"] += 1
            else:
                conflict_counts["high"] += 1

        lines.append(
            "Clarity profile (from cross-reviewer agreement): "
            f"{conflict_counts['total_consensus']} total-consensus group(s), "
            f"{conflict_counts['minor']} minor-variance, "
            f"{conflict_counts['moderate']} moderate-disagreement, "
            f"{conflict_counts['high']} high-conflict.\n"
        )

    lines.append("\n*Generated by Survivor (multi-reviewer, evidence-indexed).*\n")
    return "".join(lines)
