#!/usr/bin/env python3
"""
FILE: engine/render/report.py
VERSION: 0.2
PURPOSE:
Render the main human-readable report.md (experimental v0, no scores).

CONTRACT:
- Must not crash on missing adjudication details (v0 scaffold).
- Output is Markdown string.

CHANGES IN v0.2:
- Add "GSAE Symmetry (Tier C)" section when run_state["gsae"] exists.
- Deterministic reviewer-to-artifact mapping using sorted reviewers with gsae_observation.
- Show gsae_subject context if present in any reviewer pack.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.core.triage_utils import list_triage_claims


def _md_list(items: List[str]) -> str:
    if not items:
        return "- (none)\n"
    return "".join([f"- {x}\n" for x in items])


def _vote_symbol(v: str) -> str:
    # stable, compact rendering
    if v == "supported":
        return "✅ supported"
    if v == "unsupported":
        return "❌ unsupported"
    if v == "undetermined":
        return "❓ undetermined"
    return f"• {v}"


def _disagreement_score(tally: Dict[str, Any]) -> int:
    """
    Higher = more disagreement.
    Uses arena.tally keys produced by adjudicator:
      supported_votes / unsupported_votes / undetermined_votes
    """
    if not isinstance(tally, dict):
        return 0
    s = int(tally.get("supported_votes", 0) or 0)
    u = int(tally.get("unsupported_votes", 0) or 0)
    d = int(tally.get("undetermined_votes", 0) or 0)
    return (min(s, u) * 3) + d


def _truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "…"


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


# ---------------------------------------------------------------------------
# GSAE rendering
# ---------------------------------------------------------------------------

def _gsae_observation_reviewers_sorted(phase2: Dict[str, Any]) -> List[str]:
    """
    Re-derive the same reviewer ordering used by extract_gsae_observations():
    sorted(phase2 keys) filtered to packs that contain 'gsae_observation'.
    """
    out: List[str] = []
    for name in sorted(phase2.keys()):
        pack = _safe_dict(phase2.get(name))
        if "gsae_observation" in pack:
            out.append(name)
    return out


def _first_gsae_subject(phase2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    If any reviewer pack contains gsae_subject, return the first one in
    deterministic order; else None.
    """
    for name in sorted(phase2.keys()):
        pack = _safe_dict(phase2.get(name))
        subj = pack.get("gsae_subject")
        if isinstance(subj, dict):
            return subj
    return None


def _render_gsae_section(run_state: Dict[str, Any]) -> str:
    gsae = run_state.get("gsae")
    if not isinstance(gsae, dict):
        return ""  # absent => no section

    phase2 = _safe_dict(run_state.get("phase2"))
    artifacts = _safe_list(gsae.get("artifacts"))
    settings = _safe_dict(gsae.get("settings"))

    # Deterministic mapping: artifact index corresponds to sorted reviewers that have observation
    obs_reviewers = _gsae_observation_reviewers_sorted(phase2)
    obs_index = {name: i for i, name in enumerate(obs_reviewers)}

    subj = _first_gsae_subject(phase2)
    subj_label = None
    ctr_label = None
    if subj:
        subj_label = subj.get("subject_label")
        ctr_label = subj.get("counterparty_label")

    lines: List[str] = []
    lines.append("## GSAE Symmetry (Tier C)\n")

    # Settings summary
    if settings:
        ver = settings.get("version", "(missing)")
        eps = settings.get("epsilon", "(missing)")
        tau = settings.get("tau", "(missing)")
        lines.append(f"- settings: version={ver}, epsilon={eps}, tau={tau}\n")
    else:
        lines.append("- settings: (missing)\n")

    if subj_label or ctr_label:
        lines.append(f"- subject: {subj_label or '(missing)'} | counterparty: {ctr_label or '(missing)'}\n")

    lines.append(f"- artifacts: {len(artifacts)}\n\n")

    # Per-reviewer table (includes reviewers without observation)
    lines.append("| reviewer | has_observation | symmetry_status | delta | quarantine_fields |\n")
    lines.append("|---|---:|---|---:|---|\n")

    quarantined: List[str] = []

    # First, reviewers in deterministic global order
    for reviewer in sorted(phase2.keys()):
        pack = _safe_dict(phase2.get(reviewer))
        has_obs = "gsae_observation" in pack

        status = "--"
        delta = "--"
        qfields = "--"

        if has_obs:
            # Find its artifact index via dict map (matches extract_gsae_observations ordering)
            idx = obs_index.get(reviewer)

            art = None
            if idx is not None and idx < len(artifacts):
                art = artifacts[idx] if isinstance(artifacts[idx], dict) else None

            if isinstance(art, dict):
                status = str(art.get("symmetry_status", "UNKNOWN"))
                delta = art.get("delta", "--")
                qfields_raw = art.get("quarantine_fields", []) or []
                qfields = ", ".join(str(f) for f in qfields_raw) if qfields_raw else "--"
                if status == "QUARANTINE":
                    quarantined.append(reviewer)
            else:
                status = "UNKNOWN"
                delta = "--"
                qfields = "--"

        lines.append(
            f"| {reviewer} | {'yes' if has_obs else 'no'} | {status} | {delta} | {qfields} |\n"
        )

    lines.append("\n")

    # Quarantine log (best-effort, based on artifacts)
    if quarantined:
        lines.append("### Quarantine log\n")
        lines.append(f"- quarantined_reviewers: {quarantined}\n")
        lines.append(
            "- enforcer_behavior: on QUARANTINE, apply_gsae_quarantine prunes **gsae_observation** "
            "from that reviewer's Phase 2 pack **before adjudication**.\n"
        )
    else:
        lines.append("### Quarantine log\n")
        lines.append("- (none)\n")

    lines.append("\n---\n")
    return "".join(lines)


def render_report(run_state: Dict[str, Any], config: Dict[str, Any]) -> str:
    article = _safe_dict(run_state.get("article"))
    adjudicated = _safe_dict(run_state.get("adjudicated"))
    phase2 = _safe_dict(run_state.get("phase2"))

    lines: List[str] = []
    lines.append("# Survivor Report (v0)\n")
    lines.append(f"**Article ID:** {article.get('id','(unknown)')}\n")
    if article.get("source_url"):
        lines.append(f"**Source:** {article['source_url']}\n")
    if article.get("title"):
        lines.append(f"**Title:** {article['title']}\n")

    lines.append("\n---\n")

    # EvidenceBank preview (v0.5)
    lines.append("## EvidenceBank Preview (v0.5)\n")
    ev = _safe_dict(run_state.get("evidence_bank"))
    items = _safe_list(ev.get("items"))
    lines.append(f"- items: {len(items)}\n")
    lines.append(f"- used_chars: {ev.get('used_chars')}\n\n")

    preview_n = 8  # v0.5 cap
    for it in items[:preview_n]:
        it = _safe_dict(it)
        lines.append(f"- **{it.get('eid')}** (len={it.get('char_len')})\n")
        snippet = _truncate(it.get("text") or "", 300)
        lines.append(f"  - text: {snippet}\n")

    if len(items) > preview_n:
        lines.append(f"\n- ... capped at first {preview_n} EvidenceBank items (v0.5)\n")

    lines.append("\n---\n")

    # 1) Executive Epistemic Summary
    lines.append("## Executive Epistemic Summary\n")

    adjud_waj = _safe_dict(_safe_dict(adjudicated.get("article_track")).get("adjudicated_whole_article_judgment"))
    lines.append("### Adjudicated Whole-Article Judgment\n")
    lines.append(f"- classification: **{adjud_waj.get('classification','(missing)')}**\n")
    lines.append(f"- confidence: **{adjud_waj.get('confidence','(missing)')}**\n")
    lines.append(f"- evidence_eids: {adjud_waj.get('evidence_eids', [])}\n")

    lines.append("\n### Reviewer Whole-Article Judgments\n")
    for model in sorted(phase2.keys()):
        pack = _safe_dict(phase2.get(model))
        waj = _safe_dict(pack.get("whole_article_judgment"))
        cls = waj.get("classification", "(missing)")
        conf = waj.get("confidence", "(missing)")
        eids = waj.get("evidence_eids", [])
        lines.append(f"- **{model}**: {cls} (confidence: {conf})  \n  evidence_eids: {eids}\n")

    lines.append("\n---\n")

    # INSERT: GSAE section (Task 17 Step 1/2)
    gsae_section = _render_gsae_section(run_state)
    if gsae_section:
        lines.append(gsae_section)

    # 2) Major Claims (by model, v0)
    lines.append("## Major Claims (by reviewer, v0)\n")
    for model in sorted(phase2.keys()):
        pack = _safe_dict(phase2.get(model))
        claims = list_triage_claims(pack)
        lines.append(f"### {model}\n")
        if not claims:
            lines.append("- (none)\n")
            continue
        for c in claims:
            c = _safe_dict(c)
            lines.append(
                f"- **{c.get('claim_id')}** (type={c.get('type')}, centrality={c.get('centrality')})\n"
                f"  - text: {c.get('text')}\n"
                f"  - evidence_eids: {c.get('evidence_eids', [])}\n"
            )

    lines.append("\n---\n")
    lines.append("## Claim Arena (adjudicated groups, v0.3)\n")
    arena = _safe_dict(_safe_dict(adjudicated.get("claim_track")).get("arena"))
    claims = _safe_list(arena.get("adjudicated_claims"))
    lines.append(f"- groups_count: {arena.get('groups_count')}\n")
    lines.append(f"- near_duplicate_edges: {len(_safe_list(arena.get('edges')))}\n\n")

    if not claims:
        lines.append("- (none)\n")
    else:
        for g in claims[:20]:
            g = _safe_dict(g)
            lines.append(
                f"- **{g.get('adjudication')}** | group_id: {g.get('group_id')} | members: {g.get('member_claim_ids')}\n"
            )
            lines.append(f"  - text: {g.get('text')}\n")
            lines.append(f"  - evidence_eids: {g.get('evidence_eids')}\n")
            lines.append(f"  - reviewer_votes: {g.get('reviewer_votes')}\n")
            lines.append(f"  - tally: {g.get('tally')}\n")

    lines.append("\n---\n")
    lines.append("## Disagreement Radar (claim groups, v0.7)\n")

    if not claims:
        lines.append("- (none)\n")
    else:
        scored = []
        for g in claims:
            g = _safe_dict(g)
            scored.append((-_disagreement_score(_safe_dict(g.get("tally"))), str(g.get("group_id", "")), g))
        scored.sort()

        max_show = 15  # v0.7 cap
        shown = 0

        for _neg_score, _gid, g in scored:
            if shown >= max_show:
                lines.append(f"\n- ... capped at top {max_show} disagreement groups (v0.7)\n")
                break

            tally = _safe_dict(g.get("tally"))
            rv = _safe_dict(g.get("reviewer_votes"))

            score = _disagreement_score(tally)
            if score <= 0:
                continue

            lines.append(
                f"- **group_id:** {g.get('group_id')} | adjudication: **{g.get('adjudication')}** | disagreement_score: **{score}**\n"
            )
            lines.append(f"  - text: {g.get('text')}\n")
            lines.append(f"  - members: {g.get('member_claim_ids')}\n")
            lines.append(f"  - evidence_eids: {g.get('evidence_eids')}\n")
            lines.append(f"  - tally: {tally}\n")

            for model in sorted(phase2.keys()):
                vv = rv.get(model)
                vote_str = vv.get("vote") if isinstance(vv, dict) else vv
                lines.append(f"  - {model}: {_vote_symbol(str(vote_str) if vote_str is not None else '(missing)')}\n")

            shown += 1

        if shown == 0:
            lines.append("- (none)\n")

    lines.append("\n---\n")

    # 3) Structured Disagreements (article track)
    lines.append("## Structured Disagreements (article track)\n")
    disag = _safe_list(
        _safe_dict(
            _safe_dict(adjudicated.get("article_track")).get("adjudicated_whole_article_judgment")
        ).get("disagreements")
    )
    if not disag:
        lines.append("- (none)\n")
    else:
        for d in disag:
            d = _safe_dict(d)
            lines.append(f"- classification: **{d.get('classification')}** | models: {d.get('models')} | score: {d.get('score')}\n")

    lines.append("\n---\n")

    # 4) Counterfactual Requirements (by reviewer)
    lines.append("## Counterfactual Evidence Requirements (by reviewer)\n")
    for model in sorted(phase2.keys()):
        pack = _safe_dict(phase2.get(model))
        cfs = _safe_list(pack.get("counterfactual_requirements"))
        lines.append(f"### {model}\n")
        if not cfs:
            lines.append("- (none)\n")
            continue
        for cf in cfs:
            cf = _safe_dict(cf)
            lines.append(
                f"- target_claim_id: **{cf.get('target_claim_id')}**\n"
                f"  - type: {cf.get('counterfactual_type')}\n"
                f"  - measurable_type: {cf.get('measurable_type')}\n"
                f"  - description: {cf.get('description')}\n"
                f"  - why: {cf.get('why_it_changes_confidence')}\n"
                f"  - confidence: {cf.get('confidence')}\n"
            )

    lines.append("\n---\n")

    # 5) Tickets (v0.5): show adjudicated claim-group tickets + carry-forward article tickets
    lines.append("## Tickets (v0.5)\n")
    tickets = _safe_list(adjudicated.get("final_tickets"))
    lines.append(f"- total: {len(tickets)}\n\n")

    def _ticket_sort_key(t: Dict[str, Any]) -> str:
        return f"{t.get('ticket_type','')}|{t.get('ticket_id','')}"

    shown = 0
    max_show = 30  # v0.5 cap

    for t in sorted([_safe_dict(x) for x in tickets], key=_ticket_sort_key):
        if shown >= max_show:
            lines.append(f"\n- ... capped at {max_show} tickets (v0.5)\n")
            break

        tt = t.get("ticket_type", "unknown")
        tid = t.get("ticket_id", "(missing)")
        lines.append(f"- **{tid}** ({tt})\n")

        if tt == "claim_group":
            lines.append(f"  - adjudication: {t.get('adjudication')}\n")
            lines.append(f"  - group_id: {t.get('group_id')}\n")
            lines.append(f"  - member_claim_ids: {t.get('member_claim_ids')}\n")
            lines.append(f"  - claim_text: {t.get('claim_text')}\n")
            lines.append(f"  - claim_type: {t.get('claim_type')}\n")
            lines.append(f"  - centrality: {t.get('centrality')}\n")
            lines.append(f"  - evidence_eids: {t.get('evidence_eids')}\n")
            lines.append(f"  - reviewer_votes: {t.get('reviewer_votes')}\n")
            lines.append(f"  - tally: {t.get('tally')}\n")
        else:
            if "summary" in t:
                lines.append(f"  - summary: {t.get('summary')}\n")
            if "category" in t:
                lines.append(f"  - category: {t.get('category')}\n")
            if "evidence_eids" in t:
                lines.append(f"  - evidence_eids: {t.get('evidence_eids')}\n")

        shown += 1

    lines.append("\n---\n")

    # 6) Authority Verification
    lines.append("## Authority Verification\n")
    verification = _safe_dict(run_state.get("verification"))
    v_enabled = bool(verification.get("enabled", False))

    if not v_enabled:
        lines.append("- verification_enabled: false (skipped)\n")
    else:
        v_results = _safe_list(verification.get("results"))
        v_note = verification.get("note")

        if v_note:
            lines.append(f"- note: {v_note}\n")

        lines.append(f"- results_count: {len(v_results)}\n")

        if v_results:
            status_counts: Dict[str, int] = {}
            for r in v_results:
                r = _safe_dict(r)
                s = r.get("verification_status", "(missing)")
                status_counts[s] = status_counts.get(s, 0) + 1
            lines.append("- status_counts:\n")
            for s in sorted(status_counts):
                lines.append(f"  - {s}: {status_counts[s]}\n")

            max_show = int(config.get("verification_max_claims", 20))
            lines.append(f"\n### Top {min(max_show, len(v_results))} Verification Results\n")
            for r in v_results[:max_show]:
                r = _safe_dict(r)
                src_count = len(_safe_list(r.get("authority_sources")))
                lines.append(
                    f"- **{r.get('claim_id')}** ({r.get('claim_kind')}) "
                    f"| status: **{r.get('verification_status')}** "
                    f"| confidence: {r.get('confidence')} "
                    f"| sources: {src_count}\n"
                )
                lines.append(f"  - text: {r.get('claim_text')}\n")
                lines.append(f"  - method: {r.get('method_note')}\n")

            if len(v_results) > max_show:
                lines.append(f"\n- ... capped at {max_show} verification results\n")

    return "".join(lines)
