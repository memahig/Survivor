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

from engine.core.triage_utils import list_triage_claims


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
    Build claim_id -> {centrality, type, reviewer} from phase2 triage claims.
    Used to approximate "centrality-first" without inventing anything.
    """
    idx: Dict[str, Dict[str, Any]] = {}
    for reviewer in sorted(phase2.keys()):
        pack = _sd(phase2.get(reviewer))
        for c in list_triage_claims(pack):
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


def _compute_conflict_counts(groups: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count claim groups by disagreement bucket."""
    counts = {"total_consensus": 0, "minor": 0, "moderate": 0, "high": 0}
    for g in groups:
        score = _disagreement_score(_sd(g.get("tally")))
        desc = _disagreement_descriptor(score)
        if desc == "total consensus":
            counts["total_consensus"] += 1
        elif desc == "minor interpretive variance":
            counts["minor"] += 1
        elif desc == "moderate disagreement":
            counts["moderate"] += 1
        else:
            counts["high"] += 1
    return counts


# ---------------------------------------------------------------------------
# Plain Language Synthesis (deterministic, no LLM)
# ---------------------------------------------------------------------------

_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def _reviewer_conclusion_sentence(
    name: str,
    classification: str,
    confidence: str,
) -> str:
    """One-sentence summary of what a reviewer concluded."""
    cl = classification or "unknown"
    if confidence == "high":
        return f"**{name.title()}** sees this as **{cl}**."
    if confidence == "medium":
        return f"**{name.title()}** sees this as **{cl}**, with moderate confidence."
    if confidence == "low":
        return f"**{name.title()}** leans toward **{cl}**, with low confidence."
    return f"**{name.title()}** sees this as **{cl}**."


def _top_counterfactuals(
    cfs: List[Dict[str, Any]],
    claim_index: Dict[str, Dict[str, Any]],
    n: int = 1,
) -> List[str]:
    """Pick top-N counterfactuals by confidence, return prose fragments."""
    if not cfs:
        return []
    ranked = sorted(cfs, key=lambda c: _CONFIDENCE_ORDER.get(
        str(_sd(c).get("confidence", "")).lower(), 9
    ))
    out: List[str] = []
    for cf in ranked[:n]:
        cf = _sd(cf)
        why = _s(cf.get("why_it_changes_confidence") or cf.get("description") or "")
        if not why:
            continue
        # Lowercase first char for mid-sentence use
        why_lower = why[0].lower() + why[1:] if why else why
        why_lower = _truncate(why_lower, 140)
        out.append(why_lower)
    return out


def _render_plain_language_synthesis(
    phase2: Dict[str, Any],
    adjudicated: Dict[str, Any],
    groups: List[Dict[str, Any]],
    conflict_counts: Dict[str, int],
    gsae: Any,
    claim_index: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> str:
    """
    Deterministic plain-language synthesis from structured adjudicated output.
    Four blocks: per-reviewer, agreement, caution, synthesis.
    """
    lines: List[str] = []
    lines.append("## What the reviewers found\n\n")

    reviewers = sorted(phase2.keys())
    n_reviewers = len(reviewers)

    # ---- Block 1: What each reviewer concluded ----
    for name in reviewers:
        pack = _sd(phase2.get(name))
        r_waj = _sd(pack.get("whole_article_judgment"))
        cls = _s(r_waj.get("classification"))
        conf = _s(r_waj.get("confidence")).lower()

        sentence = _reviewer_conclusion_sentence(name, cls, conf)

        cfs = _sl(pack.get("counterfactual_requirements"))
        if cfs:
            top = _top_counterfactuals(cfs, claim_index, n=1)
            if top:
                sentence += f" It raises {len(cfs)} verification concern(s) \u2014 notably that {top[0]}."
            else:
                sentence += f" It raises {len(cfs)} verification concern(s)."
        else:
            sentence += " It does not raise additional verification concerns."

        lines.append(f"- {sentence}\n")

    lines.append("\n")

    # ---- Block 2: Where they agree ----
    classifications = {}
    for name in reviewers:
        pack = _sd(phase2.get(name))
        cls = _s(_sd(pack.get("whole_article_judgment")).get("classification")).lower()
        classifications.setdefault(cls, []).append(name.title())

    if len(classifications) == 1:
        cls_val = list(classifications.keys())[0]
        lines.append(
            f"All {n_reviewers} reviewers classify this as **{cls_val}**."
        )
    else:
        parts = []
        for cls_val, names in sorted(classifications.items(), key=lambda x: -len(x[1])):
            parts.append(f"{' and '.join(names)}: {cls_val}")
        lines.append("Reviewers split \u2014 " + "; ".join(parts) + ".")

    total = len(groups)
    tc = conflict_counts["total_consensus"]
    if total > 0:
        if tc == total:
            lines.append(f" All {total} claim group(s) reached total consensus.")
        else:
            remainder = total - tc
            # Find the dominant non-consensus descriptor
            if conflict_counts["high"] > 0:
                rem_desc = "high structural conflict"
            elif conflict_counts["moderate"] > 0:
                rem_desc = "moderate disagreement"
            else:
                rem_desc = "minor interpretive variance"
            lines.append(
                f" {tc} of {total} claim group(s) reached total consensus; "
                f"{remainder} show {rem_desc}."
            )
    lines.append("\n\n")

    # ---- Block 3: Where caution is raised ----
    all_cfs: List[Dict[str, Any]] = []
    for name in reviewers:
        pack = _sd(phase2.get(name))
        for cf in _sl(pack.get("counterfactual_requirements")):
            cf = _sd(cf)
            cf_copy = dict(cf)
            cf_copy["_reviewer"] = name
            all_cfs.append(cf_copy)

    if not all_cfs:
        lines.append("No reviewers flagged specific verification gaps.\n\n")
    else:
        # Sort by confidence (high first), cap at 3
        ranked = sorted(all_cfs, key=lambda c: _CONFIDENCE_ORDER.get(
            str(c.get("confidence", "")).lower(), 9
        ))
        items = ranked[:3]

        # Count distinct reviewers with CFs
        cf_reviewers = sorted(set(c["_reviewer"] for c in all_cfs))
        lines.append(
            f"{len(cf_reviewers)} reviewer(s) ({', '.join(r.title() for r in cf_reviewers)}) "
            f"raise verification concerns:\n\n"
        )
        for cf in items:
            reviewer = cf["_reviewer"].title()
            why = _s(cf.get("why_it_changes_confidence") or cf.get("description") or "")
            target_id = _s(cf.get("target_claim_id"))
            claim_rec = claim_index.get(target_id, {})
            claim_text = _truncate(_s(claim_rec.get("text", "")), 80)

            if why and claim_text:
                lines.append(f"- {reviewer} notes: {_truncate(why, 140)} (re: \"{claim_text}\")\n")
            elif why:
                lines.append(f"- {reviewer} notes: {_truncate(why, 140)}\n")

        lines.append("\n")

    # ---- Block 4: How Survivor combined it ----
    total_claims = sum(
        len(list_triage_claims(_sd(phase2.get(name))))
        for name in reviewers
    )

    consensus_line = ""
    if total > 0:
        if tc == total:
            consensus_line = f"total consensus on all {total}"
        else:
            consensus_line = f"total consensus on {tc} of {total}"

    # Symmetry line
    symmetry_line = ""
    if isinstance(gsae, dict):
        artifacts = _sl(gsae.get("artifacts"))
        q_count = sum(
            1 for a in artifacts
            if _sd(a).get("symmetry_status") == "QUARANTINE"
        )
        f_count = sum(
            1 for a in artifacts
            if _sd(a).get("symmetry_status") == "SOFT_FLAG"
        )
        if q_count > 0:
            symmetry_line = f"symmetry flagged {q_count} reviewer(s) for quarantine"
        elif f_count > 0:
            symmetry_line = f"symmetry soft-flagged {f_count} reviewer(s)"
        else:
            symmetry_line = "no symmetry violations detected"
    else:
        symmetry_line = "symmetry not assessed"

    # Conclusion line
    waj = _sd(_sd(adjudicated.get("article_track")).get("adjudicated_whole_article_judgment"))
    adj_cls = _s(waj.get("classification")) or "unknown"

    if tc == total and "quarantine" not in symmetry_line.lower():
        conclusion = f"stable **{adj_cls}** with no structural distortion detected"
    elif conflict_counts["high"] > 0:
        conclusion = f"**{adj_cls}** with high structural conflict across reviewers"
    elif conflict_counts["moderate"] > 0:
        conclusion = f"**{adj_cls}** with moderate disagreement across reviewers"
    elif "quarantine" in symmetry_line.lower():
        conclusion = f"potential asymmetry detected in **{adj_cls}** \u2014 review symmetry analysis"
    else:
        conclusion = f"**{adj_cls}** with minor interpretive variance"

    lines.append(
        f"Survivor grouped {total_claims} individual claims into "
        f"{total} claim group(s), checked cross-reviewer agreement, "
        f"and found {consensus_line}. "
        f"{symmetry_line.capitalize()}. "
        f"Conclusion: {conclusion}.\n"
    )

    lines.append("\n---\n")
    return "".join(lines)


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

    # Divergence radar
    radar = _sd(run_state.get("divergence_radar"))
    divergence: Dict[str, Any] = {"status": "not_run"}
    if radar.get("status") == "run":
        divergence = {
            "status": "run",
            "whole_article_conflict": radar.get("whole_article_conflict"),
            "central_claim_instability": radar.get("central_claim_instability"),
            "unsupported_core_rate": radar.get("unsupported_core_rate"),
            "undetermined_core_rate": radar.get("undetermined_core_rate"),
            "gsae_quarantine_count": radar.get("gsae_quarantine_count"),
            "notes": _sl(radar.get("notes")),
        }

    # Plain language synthesis (structured)
    pls_reviewers = []
    for name in sorted(phase2.keys()):
        pack = _sd(phase2.get(name))
        r_waj = _sd(pack.get("whole_article_judgment"))
        cfs = _sl(pack.get("counterfactual_requirements"))
        pls_reviewers.append({
            "reviewer": name,
            "classification": r_waj.get("classification"),
            "confidence": r_waj.get("confidence"),
            "counterfactual_count": len(cfs),
        })

    conflict_counts = _compute_conflict_counts(groups)
    plain_language = {
        "per_reviewer": pls_reviewers,
        "agreement": {
            "classification_unanimous": len(set(
                _s(_sd(phase2.get(n)).get("whole_article_judgment", {}).get("classification"))
                for n in phase2
            )) <= 1,
            "total_consensus_groups": conflict_counts["total_consensus"],
            "total_groups": len(groups),
        },
        "caution": {
            "reviewers_with_concerns": [
                name for name in sorted(phase2.keys())
                if _sl(_sd(phase2.get(name)).get("counterfactual_requirements"))
            ],
            "total_concerns": sum(
                len(_sl(_sd(phase2.get(n)).get("counterfactual_requirements")))
                for n in phase2
            ),
        },
        "synthesis": {
            "total_claims": sum(
                len(list_triage_claims(_sd(phase2.get(n))))
                for n in phase2
            ),
            "total_groups": len(groups),
            "conflict_counts": conflict_counts,
        },
    }

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
        "plain_language_synthesis": plain_language,
        "commented_lines": commented,
        "symmetry": symmetry,
        "divergence_radar": divergence,
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

    # ---- Claims / groups (compute early for synthesis + bottom line) ----
    arena = _sd(_sd(adjudicated.get("claim_track")).get("arena"))
    groups = [_sd(g) for g in _sl(arena.get("adjudicated_claims"))]
    conflict_counts = _compute_conflict_counts(groups)

    # Derive support counts from group-level vote tallies, not adjudication labels.
    # adjudication is kept/rejected/downgraded; votes are supported/unsupported.
    supported = []
    unsupported = []
    undetermined = []
    for g in groups:
        tally = _sd(g.get("tally"))
        s = tally.get("supported_votes", 0)
        u = tally.get("unsupported_votes", 0)
        if s > u:
            supported.append(g)
        elif u > s:
            unsupported.append(g)
        else:
            undetermined.append(g)

    # ---- Plain language synthesis ----
    gsae = run_state.get("gsae")
    lines.append(_render_plain_language_synthesis(
        phase2, adjudicated, groups, conflict_counts, gsae, claim_index, config,
    ))

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

    # ---- Divergence radar ----
    radar = _sd(run_state.get("divergence_radar"))
    if radar.get("status") == "run":
        lines.append("## Divergence radar\n")

        wac = radar.get("whole_article_conflict", "low")
        cci = radar.get("central_claim_instability", "low")
        qcount = radar.get("gsae_quarantine_count", 0)

        lines.append(f"- Whole-article stability: **{wac}**\n")
        lines.append(f"- Core-claim stability: **{cci}**\n")

        unsup_rate = radar.get("unsupported_core_rate", 0.0)
        undet_rate = radar.get("undetermined_core_rate", 0.0)
        if unsup_rate > 0 or undet_rate > 0:
            lines.append(
                f"  - Unsupported core rate: {unsup_rate:.0%}, "
                f"undetermined core rate: {undet_rate:.0%}\n"
            )

        if qcount > 0:
            lines.append(
                f"- Symmetry enforcement: **Quarantine occurred** "
                f"({qcount} reviewer(s) removed from symmetry pool)\n"
            )
        else:
            lines.append("- Symmetry enforcement: No quarantines\n")

        radar_notes = _sl(radar.get("notes"))
        if radar_notes:
            lines.append("\n")
            for note in radar_notes:
                lines.append(f"  > {_s(note)}\n")

        # Net effect summary
        if wac == "high" or cci == "high":
            lines.append(
                "\n**Net effect:** This run cannot recover a single stable story "
                "without revisiting the source evidence anchors.\n"
            )
        elif wac == "moderate" or cci == "moderate":
            lines.append(
                "\n**Net effect:** Partial convergence. Some claims are stable, "
                "but the overall interpretation has unresolved variance.\n"
            )
        else:
            lines.append(
                "\n**Net effect:** Reviewers converge. The recovered story structure "
                "is stable within normal interpretive variance.\n"
            )

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
        cc = _compute_conflict_counts(groups)

        lines.append(
            "Clarity profile (from cross-reviewer agreement): "
            f"{cc['total_consensus']} total-consensus group(s), "
            f"{cc['minor']} minor-variance, "
            f"{cc['moderate']} moderate-disagreement, "
            f"{cc['high']} high-conflict.\n"
        )

    lines.append("\n*Generated by Survivor (multi-reviewer, evidence-indexed).*\n")
    return "".join(lines)
