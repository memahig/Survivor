#!/usr/bin/env python3
"""
FILE: engine/render/debug_report.py
VERSION: 0.1
PURPOSE:
Render debug.md (auditable engineering output).

CONTRACT:
- Must be stable and verbose.
- Focuses on counts, caps, and key structural artifacts.
"""

from __future__ import annotations

from typing import Any, Dict, List




def render_debug(run_state: Dict[str, Any], config: Dict[str, Any]) -> str:
    ev = run_state.get("evidence_bank", {})
    phase1 = run_state.get("phase1", {})
    phase2 = run_state.get("phase2", {})

    lines: List[str] = []
    lines.append("# Survivor Debug Report (v0)\n\n")

    lines.append("## Config\n")
    lines.append(f"- max_chars: {config.get('max_chars')}\n")
    lines.append(f"- max_claims_per_reviewer: {config.get('max_claims_per_reviewer')}\n")
    lines.append(f"- max_near_duplicate_links: {config.get('max_near_duplicate_links')}\n")
    lines.append(f"- decision_margin: {config.get('decision_margin')}\n")

    # Reviewer participation
    reviewer_status = run_state.get("reviewer_status", {})
    lines.append(f"- min_reviewers_required: {config.get('min_reviewers_required')}\n")
    lines.append(f"\n## Reviewer Participation\n")
    if reviewer_status:
        for name, info in reviewer_status.items():
            status = info.get("status", "unknown")
            error_type = info.get("error_type")
            stage = info.get("stage", "")
            fallback = info.get("fallback", "")
            prev = info.get("previous_status", "")
            detail_parts = []
            if error_type:
                detail_parts.append(error_type)
            if stage:
                detail_parts.append(f"stage={stage}")
            if fallback:
                detail_parts.append(f"fallback={fallback}")
            if prev:
                detail_parts.append(f"previous={prev}")
            detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
            lines.append(f"- **{name}**: {status}{detail}\n")
    else:
        for name in phase1.keys():
            lines.append(f"- **{name}**: ok\n")

    lines.append("\n## EvidenceBank\n")
    lines.append(f"- used_chars: {ev.get('used_chars')}\n")
    items = ev.get("items", [])
    lines.append(f"- items: {len(items)}\n")
    for it in items:
        lines.append(f"  - {it.get('eid')} len={it.get('char_len')}\n")

    lines.append("\n## Phase 1 counts\n")
    for m, pack in phase1.items():
        lines.append(f"### {m}\n")
        lines.append(f"- claims: {len(pack.get('claims', []))}\n")
        lines.append(f"- article_tickets: {len(pack.get('article_tickets', []))}\n")
        lines.append(f"- claim_tickets: {len(pack.get('claim_tickets', []))}\n")

    lines.append("\n## Phase 2 counts\n")
    for m, pack in phase2.items():
        lines.append(f"### {m}\n")
        lines.append(f"- claims: {len(pack.get('claims', []))}\n")
        lines.append(f"- cross_claim_votes: {len(pack.get('cross_claim_votes', []))}\n")
        lines.append(f"- article_tickets: {len(pack.get('article_tickets', []))}\n")
        lines.append(f"- claim_tickets: {len(pack.get('claim_tickets', []))}\n")

    # Tickets
    lines.append("\n## Tickets\n")
    adjudicated = run_state.get("adjudicated", {})
    final_tickets = adjudicated.get("final_tickets", [])
    lines.append(f"- final_tickets_total: {len(final_tickets)}\n")

    by_type: Dict[str, int] = {}
    for t in final_tickets:
        tt = t.get("ticket_type", "unknown")
        by_type[tt] = by_type.get(tt, 0) + 1

    for tt in sorted(by_type.keys()):
        lines.append(f"- {tt}: {by_type[tt]}\n")

    lines.append("\n## Validator\n")
    lines.append("- status: run_state validated (if this file exists, validator passed)\n")

    return "".join(lines)