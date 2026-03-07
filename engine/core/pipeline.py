#!/usr/bin/env python3
"""
FILE: engine/core/pipeline.py
VERSION: 0.5
PURPOSE:
Primary execution spine for Survivor.

FLOW:
Ingest → Normalize → EvidenceBank →
Pass 1 Triage (all reviewers) → Build Argument Spine →
Pass 2 Enrichment (all reviewers, receives spine) → Merge →
Cross-Review Payload → Phase 2 Reviewers →
Adjudication → Validation → Render Outputs

v0.5 CHANGE:
- Two-pass Phase 1: skeletal triage + enrichment with cross-reviewer spine.
  Prevents JSON truncation and streaming timeouts from monolithic prompts.
"""

from __future__ import annotations

import json
import os
import sys
import time

from typing import Optional, Dict, Any, List, Callable

from engine.core.config_loader import load_config
from engine.core.ingest import ingest_input
from engine.core.normalize import normalize_text
from engine.core.evidence_bank import build_evidence_bank
from engine.core.adjudicator import adjudicate
from engine.core.errors import ReviewerPackCompileError
from engine.core.translator import compile_reviewer_pack
from engine.core.spine_builder import build_argument_spine
from engine.core.validators import validate_run
from engine.render.report import render_report
from engine.render.debug_report import render_debug
from engine.verify.router import run_verification
from engine.core.divergence_radar import compute_divergence_radar
from engine.eo.gsae_apply import apply_gsae_quarantine
from engine.eo.gsae_process import run_gsae_tier_c

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


def _write_compile_error_report(error: ReviewerPackCompileError, outdir: str) -> None:
    """Write compile_error.json debug artifact on translator failure."""
    path = os.path.join(outdir, "compile_error.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(error.to_debug_dict(), f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass  # best-effort; don't mask the original error

    # Always print to stderr so Streamlit Cloud logs capture it.
    try:
        d = error.to_debug_dict()
        print(
            f"[COMPILE_ERROR] reviewer={d['reviewer_id']} attempt={d['attempt']}",
            file=sys.stderr,
        )
        print(
            "[COMPILE_ERROR] validation_errors=" + json.dumps(d["validation_errors"], default=str),
            file=sys.stderr,
        )
        print(
            "[COMPILE_ERROR] translation_trace=" + json.dumps(d["translation_trace"], default=str),
            file=sys.stderr,
        )
    except Exception:
        pass


def _build_reviewers_from_config(config: Dict[str, Any]) -> List[Any]:
    enabled = config.get("reviewers_enabled", [])
    if not isinstance(enabled, list) or not enabled:
        raise RuntimeError("config.reviewers_enabled must be a non-empty list")

    # Registry: config key -> factory producing a reviewer instance
    registry: Dict[str, Callable[[], Any]] = {
        # mocks (safe now)
        "mock_openai": lambda: MockReviewer("mock_openai"),
        "mock_gemini": lambda: MockReviewer("mock_gemini"),
        "mock_claude": lambda: MockReviewer("mock_claude"),
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


def _write_status(outdir: str, stage: str, detail: str = "") -> None:
    """Write pipeline_status.json for Streamlit to read during execution."""
    path = os.path.join(outdir, "pipeline_status.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"stage": stage, "detail": detail, "t": time.time()}, f)
    except Exception:
        pass


def run_pipeline(url: Optional[str], textfile: Optional[str], outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)

    _write_status(outdir, "init", "loading config")
    config = load_config()

    _write_status(outdir, "ingest", "fetching article")
    article = ingest_input(url=url, textfile=textfile)
    normalized = normalize_text(article["text"])

    _write_status(outdir, "evidence_bank", "building evidence bank")
    evidence_bank = build_evidence_bank(normalized, config)

    available_eids = [
        it["eid"] for it in evidence_bank.get("items", [])
        if isinstance(it, dict) and isinstance(it.get("eid"), str)
    ]

    reviewers = _build_reviewers_from_config(config)
    reviewer_names = [r.name for r in reviewers]
    _write_status(outdir, "reviewers_built", f"reviewers: {reviewer_names}")

    # ---------------------------
    # Phase 1, Pass 1: Skeletal Triage
    # ---------------------------
    triage_outputs: Dict[str, Any] = {}

    for reviewer in reviewers:
        _write_status(outdir, "phase1_triage", f"reviewer={reviewer.name} started")
        inp = ReviewerInputs(
            article_id=article["id"],
            source_url=article.get("source_url"),
            title=article.get("title"),
            normalized_text=normalized,
            evidence_bank=evidence_bank,
            config=config,
        )
        raw_triage = reviewer.run_triage(inp)
        _write_status(outdir, "phase1_triage", f"reviewer={reviewer.name} compiling")
        try:
            compiled = compile_reviewer_pack(
                reviewer_id=reviewer.name,
                raw_pack=raw_triage,
                call_reviewer_fn=reviewer._call_json,
                config=config,
                available_eids=available_eids,
            )
        except ReviewerPackCompileError as e:
            _write_compile_error_report(e, outdir)
            raise RuntimeError(
                f"Reviewer '{reviewer.name}' failed triage compilation "
                f"after {e.attempt} attempts"
            ) from e
        triage_outputs[reviewer.name] = compiled
        _write_status(outdir, "phase1_triage", f"reviewer={reviewer.name} done")

    # ---------------------------
    # Build cross-reviewer argument spine
    # ---------------------------
    _write_status(outdir, "spine", "building argument spine")
    spine = build_argument_spine(triage_outputs)

    # ---------------------------
    # Phase 1, Pass 2: Enrichment (receives merged spine)
    # ---------------------------
    # Keys that enrichment may contribute to the final pack.
    _ENRICHMENT_KEYS = frozenset({
        "scope_markers", "causal_links", "article_patterns",
        "omission_candidates", "counterfactual_requirements",
        "claim_omissions", "article_omissions", "framing_omissions",
        "argument_summary", "object_discipline_check",
        "rival_narratives",
        "argument_integrity",
    })

    phase1_outputs: Dict[str, Any] = {}

    for reviewer in reviewers:
        _write_status(outdir, "phase1_enrichment", f"reviewer={reviewer.name} started")
        inp = ReviewerInputs(
            article_id=article["id"],
            source_url=article.get("source_url"),
            title=article.get("title"),
            normalized_text=normalized,
            evidence_bank=evidence_bank,
            config=config,
        )
        enrichment = reviewer.run_enrichment(inp, spine)

        # Merge enrichment into triage pack
        merged = dict(triage_outputs[reviewer.name])
        for k, v in enrichment.items():
            if k in _ENRICHMENT_KEYS:
                merged[k] = v

        phase1_outputs[reviewer.name] = merged
        _write_status(outdir, "phase1_enrichment", f"reviewer={reviewer.name} done")

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
        _write_status(outdir, "phase2", f"reviewer={reviewer.name} started")
        inp = ReviewerInputs(
            article_id=article["id"],
            source_url=article.get("source_url"),
            title=article.get("title"),
            normalized_text=normalized,
            evidence_bank=evidence_bank,
            config=config,
        )
        raw_pack = reviewer.run_phase2(inp, cross_payload)
        _write_status(outdir, "phase2", f"reviewer={reviewer.name} compiling")
        try:
            compiled = compile_reviewer_pack(
                reviewer_id=reviewer.name,
                raw_pack=raw_pack,
                call_reviewer_fn=reviewer._call_json,
                config=config,
                available_eids=available_eids,
            )
        except ReviewerPackCompileError as e:
            _write_compile_error_report(e, outdir)
            raise RuntimeError(
                f"Reviewer '{reviewer.name}' failed Phase 2 compilation "
                f"after {e.attempt} attempts"
            ) from e
        phase2_outputs[reviewer.name] = compiled
        _write_status(outdir, "phase2", f"reviewer={reviewer.name} done")

    # Optional debug artifact (single write, after loop)
    with open(os.path.join(outdir, "phase2_outputs.json"), "w") as f:
        json.dump(phase2_outputs, f, indent=2)

    # ---------------------------
    # GSAE Tier C (post-extraction, pre-adjudication)
    # ---------------------------
    _write_status(outdir, "gsae", "running GSAE quarantine")
    gsae_block = run_gsae_tier_c(phase2_outputs, config)
    phase2_sanitized = apply_gsae_quarantine(phase2_outputs, gsae_block, config)

    # ---------------------------
    # Adjudication (uses sanitized phase2)
    # ---------------------------
    _write_status(outdir, "adjudication", "running adjudication")
    adjudicated = adjudicate(phase2_sanitized, config)

    # Structural forensics live in Phase 1 enrichment data, not Phase 2.
    # The adjudicator's internal merge uses phase2 (which lacks enrichment keys),
    # so we re-merge from phase1_outputs where the data actually lives.
    from engine.core.forensics_merge import merge_structural_forensics
    adjudicated["structural_forensics"] = merge_structural_forensics(phase1_outputs)

    run_state = {
        "article": article,
        "evidence_bank": evidence_bank,
        "phase1": phase1_outputs,
        "phase2": phase2_outputs,
        "adjudicated": adjudicated,
    }

    if gsae_block is not None:
        run_state["gsae"] = gsae_block

    _write_status(outdir, "post_adjudication", "divergence radar + verification")
    run_state["divergence_radar"] = compute_divergence_radar(run_state)
    run_state["verification"] = run_verification(run_state, config)
    validate_run(run_state, config)

    # ---------------------------
    # Outputs
    # ---------------------------
    _write_status(outdir, "writing_outputs", "writing run.json + reports")
    with open(os.path.join(outdir, config["outputs"]["run_json"]), "w") as f:
        json.dump(run_state, f, indent=2)

    with open(os.path.join(outdir, config["outputs"]["tickets_json"]), "w") as f:
        json.dump(adjudicated.get("final_tickets", []), f, indent=2)

    with open(os.path.join(outdir, config["outputs"]["main_report"]), "w") as f:
        f.write(render_report(run_state, config))

    with open(os.path.join(outdir, config["outputs"]["debug_md"]), "w") as f:
        f.write(render_debug(run_state, config))

    _write_status(outdir, "complete", "pipeline finished")