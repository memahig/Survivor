#!/usr/bin/env python3
"""
FILE: engine/render/render_bundle.py
VERSION: 1.0
PURPOSE:
Top-level entry point for rendering. Calls enrich_substrate() then both
renderers. Each independently try/except wrapped.

CONTRACT:
- Pure render: reads run_state only.
- No model calls. No recomputation beyond deterministic formatting.
- Returns (blunt_md, audit_md, enriched_substrate, error_str).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def render_all(
    run_state: Dict[str, Any],
    config: Dict[str, Any] | None = None,
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Render both reports from run_state.

    Returns: (blunt_md, audit_md, enriched_substrate, error_str)
    - blunt_md: Blunt Report markdown or None
    - audit_md: Audit Report markdown or None
    - enriched_substrate: enriched dict for Machine Trace tab, or None
    - error_str: error message if something failed, or None
    """
    cfg = config or {}
    errors = []

    # Step 1: Enrich substrate
    enriched = None
    try:
        from engine.analysis.substrate_enricher import enrich_substrate
        enriched = enrich_substrate(run_state, config=cfg)
        if not isinstance(enriched, dict):
            enriched = None
            errors.append("enrich_substrate returned non-dict")
    except Exception as e:
        errors.append(f"Substrate enrichment failed: {e!r}")

    # Fallback: use run_state directly if enrichment failed
    if enriched is None:
        enriched = dict(run_state) if isinstance(run_state, dict) else {}
        enriched["_render_bundle_fallback"] = True

    # Step 2: Blunt Report
    blunt_md = None
    try:
        from engine.render.blunt_report import render_blunt_report
        blunt_md = render_blunt_report(enriched, config=cfg)
    except Exception as e:
        errors.append(f"Blunt renderer failed: {e!r}")

    # Step 3: Audit Report
    audit_md = None
    try:
        from engine.render.audit_report import render_audit_report
        audit_md = render_audit_report(enriched, config=cfg)
    except Exception as e:
        errors.append(f"Audit renderer failed: {e!r}")

    error_str = "; ".join(errors) if errors else None
    return blunt_md, audit_md, enriched, error_str
