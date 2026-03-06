#!/usr/bin/env python3
"""
FILE: engine/render/audit_report.py
VERSION: 1.0
PURPOSE:
Full forensic Audit Report. Everything from the evaluation appears here.
No filtering, no word limit, no compression.

RULES:
- Fail-closed: each section try/except → "Not assessed." on error.
- Reads enriched_substrate only.
- Human-readable Markdown.
"""

from __future__ import annotations

from typing import Any, Dict, List

from engine.utils.text_normalizer import clean_for_report


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


# ---- Section renderers ----

def _section_article_classification(enriched: Dict[str, Any]) -> str:
    adjudicated = _sd(enriched.get("adjudicated"))
    article_track = _sd(adjudicated.get("article_track"))
    waj = _sd(article_track.get("adjudicated_whole_article_judgment"))

    lines = ["## Article Classification\n\n"]
    lines.append(f"- **Classification:** {_s(waj.get('classification')) or 'not assessed'}\n")
    lines.append(f"- **Confidence:** {_s(waj.get('confidence')) or 'not assessed'}\n")

    eids = _sl(waj.get("evidence_eids"))
    if eids:
        lines.append(f"- **Evidence EIDs:** {', '.join(str(e) for e in eids)}\n")

    tally = _sl(waj.get("tally"))
    if tally:
        lines.append(f"- **Tally:** {tally}\n")

    disagreements = _sl(waj.get("disagreements"))
    if disagreements:
        lines.append("\n**Disagreements:**\n\n")
        for d in disagreements:
            d = _sd(d)
            lines.append(
                f"- {_s(d.get('classification'))}: "
                f"models={d.get('models')}, score={d.get('score')}\n"
            )

    lines.append("\n")
    return "".join(lines)


def _section_reviewer_comparison(enriched: Dict[str, Any]) -> str:
    phase2 = _sd(enriched.get("phase2"))

    lines = ["## Reviewer Comparison\n\n"]
    if not phase2:
        lines.append("Not assessed.\n\n")
        return "".join(lines)

    lines.append("| Reviewer | Classification | Confidence | Counterfactuals |\n")
    lines.append("|----------|---------------|------------|----------------|\n")

    for name in sorted(phase2.keys()):
        pack = _sd(phase2.get(name))
        r_waj = _sd(pack.get("whole_article_judgment"))
        cls = _s(r_waj.get("classification"))
        conf = _s(r_waj.get("confidence"))
        cfs = _sl(pack.get("counterfactual_requirements"))
        lines.append(f"| {name.title()} | {cls} | {conf} | {len(cfs)} |\n")

    lines.append("\n")
    return "".join(lines)


def _section_claim_registry(enriched: Dict[str, Any]) -> str:
    adjudicated = _sd(enriched.get("adjudicated"))
    claim_track = _sd(adjudicated.get("claim_track"))
    arena = _sd(claim_track.get("arena"))
    groups = _sl(arena.get("adjudicated_claims"))

    lines = ["## Claim Registry\n\n"]
    if not groups:
        lines.append("No claims extracted.\n\n")
        return "".join(lines)

    lines.append(f"**Total claim groups:** {len(groups)}\n\n")

    for g in groups:
        g = _sd(g)
        gid = _s(g.get("group_id"))
        text = _s(g.get("text"))
        ctype = _s(g.get("type"))
        centrality = g.get("centrality", "?")
        kind = _s(g.get("claim_kind"))
        check = _s(g.get("checkability"))
        adj = _s(g.get("adjudication"))
        eids = _sl(g.get("evidence_eids"))
        members = _sl(g.get("member_claim_ids"))
        tally = _sd(g.get("tally"))
        votes = _sd(g.get("reviewer_votes"))

        lines.append(f"### {gid}\n\n")
        lines.append(f"- **Text:** {text}\n")
        lines.append(f"- **Type:** {ctype} | **Centrality:** {centrality}\n")
        lines.append(f"- **Kind:** {kind} | **Checkability:** {check}\n")
        lines.append(f"- **Adjudication:** {adj}\n")
        lines.append(f"- **Members:** {', '.join(str(m) for m in members)}\n")
        lines.append(f"- **Evidence:** {', '.join(str(e) for e in eids)}\n")

        if tally:
            lines.append(
                f"- **Tally:** supported={tally.get('supported_votes', 0)}, "
                f"unsupported={tally.get('unsupported_votes', 0)}, "
                f"undetermined={tally.get('undetermined_votes', 0)}\n"
            )

        if votes:
            vote_parts = []
            for reviewer, v in sorted(votes.items()):
                v = _sd(v)
                vote_parts.append(f"{reviewer}: {_s(v.get('vote'))} ({_s(v.get('confidence'))})")
            lines.append(f"- **Votes:** {'; '.join(vote_parts)}\n")

        lines.append("\n")

    return "".join(lines)


def _section_story_clusters(enriched: Dict[str, Any]) -> str:
    clusters = enriched.get("story_clusters")

    lines = ["## Story Clusters\n\n"]

    if isinstance(clusters, dict) and "error" in clusters:
        lines.append(f"Not assessed. Error: {clusters['error']}\n\n")
        return "".join(lines)

    clusters = _sl(clusters)
    if not clusters:
        lines.append("No story clusters formed.\n\n")
        return "".join(lines)

    for cl in clusters:
        cl = _sd(cl)
        cid = _s(cl.get("cluster_id"))
        members = _sl(cl.get("member_group_ids"))
        text = _s(cl.get("canonical_text"))
        cent = cl.get("max_centrality", "?")
        adj_summary = _sd(cl.get("adjudication_summary"))

        lines.append(f"- **{cid}:** {_truncate(text, 200)}\n")
        lines.append(f"  Members: {', '.join(str(m) for m in members)} | Centrality: {cent}\n")
        lines.append(
            f"  Adjudications: kept={adj_summary.get('kept', 0)}, "
            f"rejected={adj_summary.get('rejected', 0)}, "
            f"downgraded={adj_summary.get('downgraded', 0)}\n"
        )

    lines.append("\n")
    return "".join(lines)


def _section_load_bearing(enriched: Dict[str, Any]) -> str:
    lb = enriched.get("load_bearing")

    lines = ["## Load-Bearing Analysis\n\n"]

    if isinstance(lb, dict) and "error" in lb:
        lines.append(f"Not assessed. Error: {lb['error']}\n\n")
        return "".join(lines)

    lb = _sd(lb)
    lb_ids = _sl(lb.get("load_bearing_group_ids"))
    lb_texts = _sl(lb.get("load_bearing_texts"))
    wl_ids = _sl(lb.get("weak_link_group_ids"))
    wl_texts = _sl(lb.get("weak_link_texts"))
    fragility = _s(lb.get("argument_fragility"))
    source = _s(lb.get("source"))

    lines.append(f"- **Source:** {source}\n")
    lines.append(f"- **Argument fragility:** {fragility}\n\n")

    if lb_ids:
        lines.append("**Load-bearing claims:**\n\n")
        for gid, text in zip(lb_ids, lb_texts):
            lines.append(f"- {gid}: {_truncate(_s(text), 200)}\n")
        lines.append("\n")

    if wl_ids:
        lines.append("**Weak links:**\n\n")
        for gid, text in zip(wl_ids, wl_texts):
            lines.append(f"- {gid}: {_truncate(_s(text), 200)}\n")
        lines.append("\n")

    if not lb_ids and not wl_ids:
        lines.append("No load-bearing or weak-link claims identified.\n\n")

    return "".join(lines)


def _section_evidence_map(enriched: Dict[str, Any]) -> str:
    eb = _sd(enriched.get("evidence_bank"))
    items = _sl(eb.get("items"))

    lines = ["## Evidence Map\n\n"]
    if not items:
        lines.append("No evidence items.\n\n")
        return "".join(lines)

    lines.append(f"**Total items:** {len(items)}\n\n")
    for item in items:
        item = _sd(item)
        eid = _s(item.get("eid"))
        quote = _s(item.get("quote") or item.get("text"))
        lines.append(f"- **{eid}:** {_truncate(quote, 300)}\n")

    lines.append("\n")
    return "".join(lines)


def _section_verification(enriched: Dict[str, Any]) -> str:
    verification = _sd(enriched.get("verification"))

    lines = ["## Verification\n\n"]
    enabled = verification.get("enabled")
    if enabled is None:
        lines.append("Not assessed.\n\n")
        return "".join(lines)

    lines.append(f"- **Enabled:** {enabled}\n")
    note = _s(verification.get("note"))
    if note:
        lines.append(f"- **Note:** {note}\n")

    results = _sl(verification.get("results"))
    if results:
        lines.append(f"- **Results:** {len(results)} item(s)\n")
        for r in results:
            r = _sd(r)
            lines.append(f"  - {r}\n")

    lines.append("\n")
    return "".join(lines)


def _section_omissions(enriched: Dict[str, Any]) -> str:
    ranked = enriched.get("ranked_omissions")

    lines = ["## Omissions\n\n"]

    if isinstance(ranked, dict) and "error" in ranked:
        lines.append(f"Not assessed. Error: {ranked['error']}\n\n")
        return "".join(lines)

    ranked = _sl(ranked)
    if not ranked:
        lines.append("No omissions identified.\n\n")
        return "".join(lines)

    # Group by severity
    for severity in ("load_bearing", "important", "minor"):
        tier = [om for om in ranked if isinstance(om, dict) and om.get("severity") == severity]
        if not tier:
            continue

        lines.append(f"### {severity.replace('_', ' ').title()} ({len(tier)})\n\n")
        for om in tier:
            om = _sd(om)
            kind = _s(om.get("kind"))
            text = _s(om.get("merged_text"))
            reason = _s(om.get("reason_expected"))
            reviewers = _sl(om.get("supporting_reviewers"))
            concern = _s(om.get("concern_level"))
            sev_reason = _s(om.get("severity_reason"))

            lines.append(f"- **{kind}:** {text}\n")
            if reason:
                lines.append(f"  Reason: {reason}\n")
            lines.append(f"  Concern: {concern} | Severity: {severity} ({sev_reason})\n")
            if reviewers:
                lines.append(f"  Reviewers: {', '.join(str(r) for r in reviewers)}\n")

        lines.append("\n")

    return "".join(lines)


def _section_signal_detections(enriched: Dict[str, Any]) -> str:
    lines = ["## Signal Detections\n\n"]

    # Causal
    causal = enriched.get("causal_detections")
    if isinstance(causal, list):
        unsupported = [d for d in causal if isinstance(d, dict) and d.get("unsupported_causal")]
        if unsupported:
            lines.append(f"### Unsupported Causal Claims ({len(unsupported)})\n\n")
            for d in unsupported:
                d = _sd(d)
                lines.append(
                    f"- {_s(d.get('group_id'))}: \"{_truncate(_s(d.get('claim_text')), 200)}\" "
                    f"[patterns: {', '.join(_sl(d.get('matched_patterns')))}]\n"
                )
            lines.append("\n")

    # Baseline
    baseline = enriched.get("baseline_detections")
    if isinstance(baseline, list) and baseline:
        lines.append(f"### Missing Baseline Context ({len(baseline)})\n\n")
        for d in baseline:
            d = _sd(d)
            lines.append(
                f"- {_s(d.get('group_id'))}: \"{_truncate(_s(d.get('claim_text')), 200)}\" "
                f"[stat: {_s(d.get('stat_match'))}]\n"
            )
        lines.append("\n")

    # Official
    official = enriched.get("official_detections")
    if isinstance(official, list) and official:
        lines.append(f"### Official Assertion Reliance ({len(official)})\n\n")
        for d in official:
            d = _sd(d)
            lines.append(
                f"- {_s(d.get('group_id'))}: \"{_truncate(_s(d.get('claim_text')), 200)}\"\n"
            )
        lines.append("\n")

    # Check if anything was written beyond the header
    if len(lines) == 1:
        lines.append("No signal detections.\n\n")

    return "".join(lines)


def _section_rival_narratives(enriched: Dict[str, Any]) -> str:
    adjudicated = _sd(enriched.get("adjudicated"))
    forensics = _sd(adjudicated.get("structural_forensics"))
    rivals = _sl(forensics.get("rival_narratives"))

    lines = ["## Rival Narratives\n\n"]
    if not rivals:
        lines.append("No rival narratives constructed.\n\n")
        return "".join(lines)

    for rn in rivals:
        rn = _sd(rn)
        lens = _s(rn.get("lens"))
        summary = _s(rn.get("merged_summary"))
        fragility = _s(rn.get("structural_fragility"))
        concern = _s(rn.get("concern_level"))
        reviewers = _sl(rn.get("supporting_reviewers"))
        weakened = _sl(rn.get("claims_weakened_if_true"))

        lines.append(f"- **{lens}:** {summary}\n")
        lines.append(f"  Fragility: {fragility} | Concern: {concern}\n")
        if reviewers:
            lines.append(f"  Reviewers: {', '.join(str(r) for r in reviewers)}\n")
        if weakened:
            lines.append(f"  Claims weakened: {', '.join(str(c) for c in weakened[:5])}\n")

    # Shared blind spot
    sbs = _sd(forensics.get("shared_blind_spot_check"))
    if sbs.get("status") == "fail":
        lines.append(f"\n> **Shared blind spot warning:** {_s(sbs.get('reason'))}\n")

    lines.append("\n")
    return "".join(lines)


def _section_argument_summary(enriched: Dict[str, Any]) -> str:
    adjudicated = _sd(enriched.get("adjudicated"))
    forensics = _sd(adjudicated.get("structural_forensics"))
    arg = _sd(forensics.get("argument_summary"))

    lines = ["## Argument Summary\n\n"]
    if not arg:
        lines.append("Not assessed.\n\n")
        return "".join(lines)

    by_reviewer = _sd(arg.get("by_reviewer"))
    for reviewer in sorted(by_reviewer.keys()):
        r_data = _sd(by_reviewer.get(reviewer))
        conclusion = _s(r_data.get("main_conclusion"))
        reasons = _sl(r_data.get("supporting_reasons"))
        lines.append(f"### {reviewer.title()}\n\n")
        lines.append(f"**Main conclusion:** {conclusion}\n\n")
        if reasons:
            lines.append("**Supporting reasons:**\n\n")
            for r in reasons:
                lines.append(f"- {_s(r)}\n")
            lines.append("\n")

    missing = _sl(arg.get("merged_rival_explanations_missing"))
    if missing:
        lines.append("**Missing rival explanations:**\n\n")
        for m in missing:
            lines.append(f"- {_s(m)}\n")
        lines.append("\n")

    # Argument integrity
    ai = _sd(forensics.get("argument_integrity"))
    if ai:
        lines.append("### Argument Integrity\n\n")
        fragility_by = _sd(ai.get("argument_fragility_by_reviewer"))
        merged_frag = _s(ai.get("merged_argument_fragility"))
        lines.append(f"**Merged fragility:** {merged_frag}\n\n")

        for reviewer, frag in sorted(fragility_by.items()):
            lines.append(f"- {reviewer.title()}: {frag}\n")

        lb_ids = _sl(ai.get("load_bearing_claim_ids"))
        if lb_ids:
            lines.append(f"\n**Load-bearing claim IDs:** {', '.join(str(c) for c in lb_ids)}\n")

        wl_ids = _sl(ai.get("weak_link_claim_ids"))
        if wl_ids:
            lines.append(f"**Weak-link claim IDs:** {', '.join(str(c) for c in wl_ids)}\n")

        reasons_by = _sd(ai.get("reason_by_reviewer"))
        if reasons_by:
            lines.append("\n**Reasons:**\n\n")
            for reviewer, reason in sorted(reasons_by.items()):
                if _s(reason):
                    lines.append(f"- {reviewer.title()}: {_s(reason)}\n")

        lines.append("\n")

    return "".join(lines)


def _section_symmetry(enriched: Dict[str, Any]) -> str:
    gsae = enriched.get("gsae")

    lines = ["## Symmetry Analysis\n\n"]
    if not isinstance(gsae, dict):
        lines.append("Not assessed (module not executed in this run).\n\n")
        return "".join(lines)

    settings = _sd(gsae.get("settings"))
    artifacts = _sl(gsae.get("artifacts"))

    if settings:
        lines.append(
            f"- **Version:** {settings.get('version', '?')}\n"
            f"- **Epsilon:** {settings.get('epsilon', '?')}\n"
            f"- **Tau:** {settings.get('tau', '?')}\n\n"
        )

    # Subject labels from phase2
    phase2 = _sd(enriched.get("phase2"))
    for name in sorted(phase2.keys()):
        pack = _sd(phase2.get(name))
        subj = pack.get("gsae_subject")
        if isinstance(subj, dict):
            lines.append(
                f"- **Subject:** {_s(subj.get('subject_label'))} "
                f"vs **Counterparty:** {_s(subj.get('counterparty_label'))}\n"
            )
            break

    if artifacts:
        lines.append(f"\n**Artifacts:** {len(artifacts)}\n\n")
        for i, art in enumerate(artifacts):
            art = _sd(art)
            status = _s(art.get("symmetry_status"))
            delta = art.get("delta", "?")
            lines.append(f"- Artifact {i + 1}: status={status}, delta={delta}\n")

    lines.append("\n")
    return "".join(lines)


def _section_divergence_radar(enriched: Dict[str, Any]) -> str:
    radar = _sd(enriched.get("divergence_radar"))

    lines = ["## Divergence Radar\n\n"]
    if radar.get("status") != "run":
        lines.append("Not assessed.\n\n")
        return "".join(lines)

    lines.append(f"- **Whole-article conflict:** {radar.get('whole_article_conflict', '?')}\n")
    lines.append(f"- **Central claim instability:** {radar.get('central_claim_instability', '?')}\n")
    lines.append(f"- **Unsupported core rate:** {radar.get('unsupported_core_rate', 0):.0%}\n")
    lines.append(f"- **Undetermined core rate:** {radar.get('undetermined_core_rate', 0):.0%}\n")
    lines.append(f"- **GSAE quarantine count:** {radar.get('gsae_quarantine_count', 0)}\n")

    notes = _sl(radar.get("notes"))
    if notes:
        lines.append("\n**Notes:**\n\n")
        for note in notes:
            lines.append(f"- {_s(note)}\n")

    lines.append("\n")
    return "".join(lines)


def _section_adjudication_summary(enriched: Dict[str, Any]) -> str:
    adjudicated = _sd(enriched.get("adjudicated"))
    claim_track = _sd(adjudicated.get("claim_track"))
    arena = _sd(claim_track.get("arena"))
    groups = _sl(arena.get("adjudicated_claims"))

    lines = ["## Adjudication Summary\n\n"]
    if not groups:
        lines.append("No adjudicated claims.\n\n")
        return "".join(lines)

    total = len(groups)
    kept = sum(1 for g in groups if isinstance(g, dict) and g.get("adjudication") == "kept")
    rejected = sum(1 for g in groups if isinstance(g, dict) and g.get("adjudication") == "rejected")
    downgraded = sum(1 for g in groups if isinstance(g, dict) and g.get("adjudication") == "downgraded")

    # Support stats
    supported = sum(
        1 for g in groups
        if isinstance(g, dict)
        and isinstance(_sd(g.get("tally")).get("supported_votes"), (int, float))
        and _sd(g.get("tally")).get("supported_votes", 0)
        > _sd(g.get("tally")).get("unsupported_votes", 0)
    )
    unsupported = sum(
        1 for g in groups
        if isinstance(g, dict)
        and isinstance(_sd(g.get("tally")).get("unsupported_votes"), (int, float))
        and _sd(g.get("tally")).get("unsupported_votes", 0)
        > _sd(g.get("tally")).get("supported_votes", 0)
    )

    lines.append(f"- **Total groups:** {total}\n")
    lines.append(f"- **Kept:** {kept} | **Rejected:** {rejected} | **Downgraded:** {downgraded}\n")
    lines.append(f"- **Supported:** {supported} | **Unsupported:** {unsupported}\n")

    if total > 0:
        lines.append(f"- **Support rate:** {supported / total:.0%}\n")

    lines.append("\n")
    return "".join(lines)


# ---- Public API ----

_SECTION_RENDERERS = [
    _section_article_classification,
    _section_reviewer_comparison,
    _section_claim_registry,
    _section_story_clusters,
    _section_load_bearing,
    _section_evidence_map,
    _section_verification,
    _section_omissions,
    _section_signal_detections,
    _section_rival_narratives,
    _section_argument_summary,
    _section_symmetry,
    _section_divergence_radar,
    _section_adjudication_summary,
]


def render_audit_report(
    enriched: Dict[str, Any],
    config: Dict[str, Any] | None = None,
) -> str:
    """
    Render the full forensic Audit Report from enriched substrate.

    14 sections. No filtering. No word limit.
    Fail-closed per section.
    """
    if config is None:
        config = {}

    article = _sd(enriched.get("article"))
    title = _s(article.get("title")) or "(untitled)"
    source = _s(article.get("source_url"))

    lines = ["# Audit Report: Full Forensic Evaluation\n\n"]
    lines.append(f"**Article:** {title}\n")
    if source:
        lines.append(f"**Source:** {source}\n")
    lines.append("\n---\n\n")

    for renderer in _SECTION_RENDERERS:
        try:
            lines.append(renderer(enriched))
            lines.append("---\n\n")
        except Exception as e:
            section_name = renderer.__name__.replace("_section_", "").replace("_", " ").title()
            lines.append(f"## {section_name}\n\nNot assessed. Error: {e}\n\n---\n\n")

    lines.append("*Generated by Survivor (multi-reviewer, evidence-indexed).*\n")
    return clean_for_report("".join(lines))
