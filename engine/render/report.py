#!/usr/bin/env python3
"""
FILE: engine/render/report.py
VERSION: 0.1
PURPOSE:
Render the main human-readable report.md (experimental v0, no scores).

CONTRACT:
- Must not crash on missing adjudication details (v0 scaffold).
- Output is Markdown string.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _md_list(items: List[str]) -> str:
    if not items:
        return "- (none)\n"
    return "".join([f"- {x}\n" for x in items])


def render_report(run_state: Dict[str, Any], config: Dict[str, Any]) -> str:
    article = run_state.get("article", {})
    adjudicated = run_state.get("adjudicated", {})
    phase2 = run_state.get("phase2", {})

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
    ev = run_state.get("evidence_bank", {})
    items = ev.get("items", [])
    lines.append(f"- items: {len(items)}\n")
    lines.append(f"- used_chars: {ev.get('used_chars')}\n\n")

    preview_n = 8  # v0.5 cap
    for it in items[:preview_n]:
        lines.append(f"- **{it.get('eid')}** (len={it.get('char_len')})\n")
        snippet = (it.get("text") or "").strip()
        if len(snippet) > 300:
            snippet = snippet[:300].rstrip() + "…"
        lines.append(f"  - text: {snippet}\n")

    if len(items) > preview_n:
        lines.append(f"\n- ... capped at first {preview_n} EvidenceBank items (v0.5)\n")

    lines.append("\n---\n")
    
    # 1) Executive Epistemic Summary
    lines.append("## Executive Epistemic Summary\n")

    adjud_waj = adjudicated.get("article_track", {}).get("adjudicated_whole_article_judgment", {})
    lines.append("### Adjudicated Whole-Article Judgment\n")
    lines.append(f"- classification: **{adjud_waj.get('classification','(missing)')}**\n")
    lines.append(f"- confidence: **{adjud_waj.get('confidence','(missing)')}**\n")
    lines.append(f"- evidence_eids: {adjud_waj.get('evidence_eids', [])}\n")

    lines.append("\n### Reviewer Whole-Article Judgments\n")
    for model in ("openai", "gemini", "claude"):
        pack = phase2.get(model, {})
        waj = pack.get("whole_article_judgment", {})
        cls = waj.get("classification", "(missing)")
        conf = waj.get("confidence", "(missing)")
        eids = waj.get("evidence_eids", [])
        lines.append(f"- **{model}**: {cls} (confidence: {conf})  \n  evidence_eids: {eids}\n")

    lines.append("\n---\n")

    # 2) Major Claims (by model, v0)
    lines.append("## Major Claims (by reviewer, v0)\n")
    for model in ("openai", "gemini", "claude"):
        pack = phase2.get(model, {})
        claims = pack.get("claims", [])
        lines.append(f"### {model}\n")
        if not claims:
            lines.append("- (none)\n")
            continue
        for c in claims:
            lines.append(
                f"- **{c.get('claim_id')}** (type={c.get('type')}, centrality={c.get('centrality')})\n"
                f"  - text: {c.get('text')}\n"
                f"  - evidence_eids: {c.get('evidence_eids', [])}\n"
            )

    lines.append("\n---\n")
    lines.append("## Claim Arena (adjudicated groups, v0.3)\n")
    arena = adjudicated.get("claim_track", {}).get("arena", {})
    claims = arena.get("adjudicated_claims", [])
    lines.append(f"- groups_count: {arena.get('groups_count')}\n")
    lines.append(f"- near_duplicate_edges: {len(arena.get('edges', []))}\n\n")

    if not claims:
        lines.append("- (none)\n")
    else:
        for g in claims[:20]:
            lines.append(f"- **{g.get('adjudication')}** | group_id: {g.get('group_id')} | members: {g.get('member_claim_ids')}\n")
            lines.append(f"  - text: {g.get('text')}\n")
            lines.append(f"  - evidence_eids: {g.get('evidence_eids')}\n")
            lines.append(f"  - reviewer_votes: {g.get('reviewer_votes')}\n")
            lines.append(f"  - tally: {g.get('tally')}\n")

    # 3) Structured Disagreements (article track)
    lines.append("## Structured Disagreements (article track)\n")
    disag = adjudicated.get("article_track", {}).get("adjudicated_whole_article_judgment", {}).get("disagreements", [])
    if not disag:
        lines.append("- (none)\n")
    else:
        for d in disag:
            lines.append(f"- classification: **{d.get('classification')}** | models: {d.get('models')} | score: {d.get('score')}\n")

    lines.append("\n---\n")

    # 4) Counterfactual Requirements (by model)
    lines.append("## Counterfactual Evidence Requirements (by reviewer)\n")
    for model in ("openai", "gemini", "claude"):
        pack = phase2.get(model, {})
        cfs = pack.get("counterfactual_requirements", [])
        lines.append(f"### {model}\n")
        if not cfs:
            lines.append("- (none)\n")
            continue
        for cf in cfs:
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
    tickets = adjudicated.get("final_tickets", [])
    lines.append(f"- total: {len(tickets)}\n\n")

    # Deterministic ordering: ticket_type, then ticket_id
    def _ticket_sort_key(t: Dict[str, Any]) -> str:
        return f"{t.get('ticket_type','')}|{t.get('ticket_id','')}"

    shown = 0
    max_show = 30  # v0.5 cap

    for t in sorted(tickets, key=_ticket_sort_key):
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
            # Article tickets are passed through for now; show minimal stable fields
            if "summary" in t:
                lines.append(f"  - summary: {t.get('summary')}\n")
            if "category" in t:
                lines.append(f"  - category: {t.get('category')}\n")
            if "evidence_eids" in t:
                lines.append(f"  - evidence_eids: {t.get('evidence_eids')}\n")

        shown += 1

    return "".join(lines)