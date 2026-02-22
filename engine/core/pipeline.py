#!/usr/bin/env python3
"""
FILE: engine/core/pipeline.py
VERSION: 0.3
PURPOSE:
Primary execution spine for Survivor.

FLOW:
Ingest → Normalize → EvidenceBank → Phase1 Reviewers →
Cross-Review Payload → Phase2 Reviewers →
Adjudication → Validation → Render Outputs

v0.3 CHANGE:
- Reviewer imports for real providers are LAZY (inside factories),
  so empty/stub reviewer files do not crash the pipeline.
"""

from __future__ import annotations

import json
import os

from typing import Optional, Dict, Any, List, Callable

from engine.core.config_loader import load_config
from engine.core.ingest import ingest_input
from engine.core.normalize import normalize_text
from engine.core.evidence_bank import build_evidence_bank
from engine.core.adjudicator import adjudicate
from engine.core.validators import validate_run
from engine.render.report import render_report
from engine.render.debug_report import render_debug

from engine.reviewers.base import ReviewerInputs
from engine.reviewers.mock_reviewer import MockReviewer


def _lazy_import_openai_reviewer():
    from engine.reviewers.openai_reviewer import OpenAIReviewer  # type: ignore
    return OpenAIReviewer


def _lazy_import_gemini_reviewer():
    from engine.reviewers.gemini_reviewer import GeminiReviewer  # type: ignore
    return GeminiReviewer


def _lazy_import_claude_reviewer():
    from engine.reviewers.claude_reviewer import ClaudeReviewer  # type: ignore
    return ClaudeReviewer


def _build_reviewers_from_config(config: Dict[str, Any]) -> List[Any]:
    enabled = config.get("reviewers_enabled", [])
    if not isinstance(enabled, list) or not enabled:
        raise RuntimeError("config.reviewers_enabled must be a non-empty list")

    # Registry: config key -> factory producing a reviewer instance
    registry: Dict[str, Callable[[], Any]] = {
        # mocks (safe now)
        "mock_openai": lambda: MockReviewer("openai"),
        "mock_gemini": lambda: MockReviewer("gemini"),
        "mock_claude": lambda: MockReviewer("claude"),
        # real (lazy import; safe even if files are stubs until used)
        "openai": lambda: _lazy_import_openai_reviewer()("openai"),
        "gemini": lambda: _lazy_import_gemini_reviewer()("gemini"),
        "claude": lambda: _lazy_import_claude_reviewer()("claude"),
    }

    reviewers = []
    for key in enabled:
        if key not in registry:
            raise RuntimeError(f"Unknown reviewer in config.reviewers_enabled: {key}")
        try:
            reviewers.append(registry[key]())
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                f"Reviewer '{key}' selected but its class is not available yet. "
                f"Either switch to mock_* in config.reviewers_enabled, or implement that reviewer class. "
                f"Original error: {e}"
            ) from e

    # Fail closed if duplicate reviewer names (would overwrite phase outputs)
    names = [r.name for r in reviewers]
    if len(set(names)) != len(names):
        raise RuntimeError(f"Duplicate reviewer.name values after build: {names}")

    return reviewers


def run_pipeline(url: Optional[str], textfile: Optional[str], outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)

    config = load_config()

    article = ingest_input(url=url, textfile=textfile)
    normalized = normalize_text(article["text"])
    evidence_bank = build_evidence_bank(normalized, config)

    reviewers = _build_reviewers_from_config(config)

    # ---------------------------
    # Phase 1
    # ---------------------------
    phase1_outputs: Dict[str, Any] = {}

    for reviewer in reviewers:
        inp = ReviewerInputs(
            article_id=article["id"],
            source_url=article.get("source_url"),
            title=article.get("title"),
            normalized_text=normalized,
            evidence_bank=evidence_bank,
            config=config,
        )
        phase1_outputs[reviewer.name] = reviewer.run_phase1(inp)

    # ---------------------------
    # Cross-review payload
    # ---------------------------
    cross_payload = {
        "phase1_outputs": phase1_outputs,
        "config": config,
    }

    # ---------------------------
    # Phase 2
    # ---------------------------
    phase2_outputs: Dict[str, Any] = {}

    for reviewer in reviewers:
        inp = ReviewerInputs(
            article_id=article["id"],
            source_url=article.get("source_url"),
            title=article.get("title"),
            normalized_text=normalized,
            evidence_bank=evidence_bank,
            config=config,
        )
        phase2_outputs[reviewer.name] = reviewer.run_phase2(inp, cross_payload)

    # Optional debug artifact (single write, after loop)
    with open(os.path.join(outdir, "phase2_outputs.json"), "w") as f:
        json.dump(phase2_outputs, f, indent=2)

    # ---------------------------
    # Adjudication
    # ---------------------------
    adjudicated = adjudicate(phase2_outputs, config)

    run_state = {
        "article": article,
        "evidence_bank": evidence_bank,
        "phase1": phase1_outputs,
        "phase2": phase2_outputs,
        "adjudicated": adjudicated,
    }

    validate_run(run_state, config)

    # ---------------------------
    # Outputs
    # ---------------------------
    with open(os.path.join(outdir, config["outputs"]["run_json"]), "w") as f:
        json.dump(run_state, f, indent=2)

    with open(os.path.join(outdir, config["outputs"]["tickets_json"]), "w") as f:
        json.dump(adjudicated.get("final_tickets", []), f, indent=2)

    with open(os.path.join(outdir, config["outputs"]["main_report"]), "w") as f:
        f.write(render_report(run_state, config))

    with open(os.path.join(outdir, config["outputs"]["debug_md"]), "w") as f:
        f.write(render_debug(run_state, config))