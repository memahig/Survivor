#!/usr/bin/env python3
"""
FILE: engine/render/blunt_bundle.py
VERSION: 0.1
PURPOSE:
Single helper that converts Survivor run_state into:
- Blunt narrative Markdown
- Blunt structured JSON (when renderer available)

CONTRACT:
- Pure render: reads run_state only.
- No model calls. No recomputation beyond deterministic formatting.
- Fail-soft: returns errors as strings for display in Technical details.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from engine.render.blunt_biaslens import render_blunt_biaslens

from engine.render.blunt_biaslens import render_blunt_biaslens_json


def render_blunt_bundle(
    run_state: Dict[str, Any],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Returns: (blunt_md, blunt_json_obj, error_str)
    - blunt_md: Markdown narrative or None
    - blunt_json_obj: structured JSON dict or None (if renderer absent)
    - error_str: error message if something failed
    """
    cfg = config or {}

    try:
        blunt_md = render_blunt_biaslens(run_state, config=cfg)
    except Exception as e:
        return None, None, f"Blunt renderer error: {e!r}"

    blunt_obj = None
    try:
        blunt_obj = render_blunt_biaslens_json(run_state, config=cfg)
    except Exception as e:
        # Keep narrative working even if JSON pack fails
        return blunt_md, None, f"Blunt JSON renderer error: {e!r}"

    return blunt_md, blunt_obj, None
