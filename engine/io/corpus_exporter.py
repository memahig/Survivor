#!/usr/bin/env python3
"""
FILE: engine/io/corpus_exporter.py
VERSION: 0.1
PURPOSE:
Export a completed Survivor run as a BiasLens corpus case folder.

LOCKED CASE STANDARD (4 artifacts per case):
    1. article.json   — source text + hardened metadata
    2. reader_review.md — reader-facing report
    3. scholar_debug.md — debug/scholar report
    4. run.json        — raw structured Survivor output

CORPUS LAYOUT:
    {corpus_root}/{genre}/{year}/{month}/{case_folder}/

MANIFEST:
    {corpus_root}/manifest.json — append-only list of case summaries

RULES:
    - Export-only: never modifies analytical data
    - Fail-safe: export failure must never crash a successful run
    - Deterministic path derivation from article metadata
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Genre routing
# ---------------------------------------------------------------------------

_GENRE_MAP = {
    "reporting": "news_reporting",
    "journalism": "news_reporting",
    "news": "news_reporting",
    "advocacy": "opinion_analysis",
    "opinion": "opinion_analysis",
    "analysis": "opinion_analysis",
    "scientific": "scholarly_research",
    "scholarly": "scholarly_research",
    "research": "scholarly_research",
    "legal": "legal_material",
}


def _resolve_genre(run_state: Dict[str, Any]) -> str:
    """Derive genre from best available classification signals."""
    article = _sd(run_state.get("article"))
    adjudicated = _sd(run_state.get("adjudicated"))

    # Try article metadata first
    genre_raw = _s(article.get("genre")) or _s(article.get("classification"))

    # Fallback: adjudicated whole-article judgment
    if not genre_raw:
        waj = _sd(adjudicated.get("whole_article_judgment"))
        genre_raw = _s(waj.get("classification"))

    if not genre_raw:
        return "uncategorized"

    return _GENRE_MAP.get(genre_raw.lower(), "uncategorized")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _sd(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _s(x: Any) -> str:
    return str(x or "").strip()


def _slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    text = text.strip("_")
    return text[:max_len].rstrip("_")


def _fingerprint(text: str) -> str:
    """SHA-256 hash of raw article text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _engine_version(config: Dict[str, Any]) -> str:
    """Best-effort engine version: config → git commit → unknown."""
    v = _s(config.get("engine_version")) or _s(config.get("version"))
    if v:
        return v
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"git:{result.stdout.strip()}"
    except Exception:
        pass
    return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Case folder naming
# ---------------------------------------------------------------------------

def _derive_case_folder_name(article: Dict[str, Any]) -> str:
    """Build YYYY-MM-DD_source_topic case folder name."""
    # Date
    date_raw = _s(article.get("date")) or _s(article.get("published_date"))
    try:
        dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Source
    source = _slugify(_s(article.get("source")) or "unknown_source", max_len=30)

    # Topic from headline/title
    headline = _s(article.get("headline")) or _s(article.get("title")) or "untitled"
    topic = _slugify(headline, max_len=50)

    if not topic:
        topic = "untitled"

    return f"{date_str}_{source}_{topic}"


def _derive_year_month(article: Dict[str, Any]) -> tuple:
    """Return (year_str, month_str) from article date."""
    date_raw = _s(article.get("date")) or _s(article.get("published_date"))
    try:
        dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        return dt.strftime("%Y"), dt.strftime("%m")
    except (ValueError, AttributeError):
        now = datetime.now(timezone.utc)
        return now.strftime("%Y"), now.strftime("%m")


# ---------------------------------------------------------------------------
# Article.json builder
# ---------------------------------------------------------------------------

def _build_article_json(
    article: Dict[str, Any],
    engine_ver: str,
    captured_at: str,
) -> Dict[str, Any]:
    """Build the hardened article.json with required metadata fields."""
    text = _s(article.get("text"))
    return {
        "id": _s(article.get("id")) or None,
        "url": _s(article.get("source_url")) or _s(article.get("url")) or None,
        "source": _s(article.get("source")) or None,
        "date": _s(article.get("date")) or _s(article.get("published_date")) or None,
        "headline": _s(article.get("headline")) or _s(article.get("title")) or None,
        "title": _s(article.get("title")) or None,
        "text": text,
        "genre": _resolve_genre({"article": article}),
        "captured_at": captured_at,
        "fingerprint": _fingerprint(text) if text else None,
        "engine_version": engine_ver,
        "user_tags": [],
    }


# ---------------------------------------------------------------------------
# Manifest management
# ---------------------------------------------------------------------------

def _load_manifest(manifest_path: str) -> List[Dict[str, Any]]:
    """Load existing manifest or return empty list."""
    if not os.path.exists(manifest_path):
        return []
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_manifest(manifest_path: str, entries: List[Dict[str, Any]]) -> None:
    """Write manifest atomically (write-to-temp then rename)."""
    tmp_path = manifest_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, manifest_path)


def _manifest_entry(
    case_id: str,
    case_path: str,
    article_json: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "path": case_path,
        "genre": article_json.get("genre"),
        "source": article_json.get("source"),
        "date": article_json.get("date"),
        "headline": article_json.get("headline"),
        "fingerprint": article_json.get("fingerprint"),
        "captured_at": article_json.get("captured_at"),
        "engine_version": article_json.get("engine_version"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_corpus_case(
    run_state: Dict[str, Any],
    *,
    corpus_root: str = "biaslens-corpus",
    reader_report_md: Optional[str] = None,
    debug_report_md: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Export a completed Survivor run as a BiasLens corpus case.

    Args:
        run_state: complete pipeline run_state dict
        corpus_root: root directory for the corpus
        reader_report_md: reader-facing report text (or None for placeholder)
        debug_report_md: debug/scholar report text (or None for placeholder)
        config: pipeline config dict (for engine_version)

    Returns:
        Path to the created case folder, or None if export failed.

    This function is fail-safe: it catches all exceptions internally
    and returns None on failure.
    """
    try:
        return _export_corpus_case_inner(
            run_state,
            corpus_root=corpus_root,
            reader_report_md=reader_report_md,
            debug_report_md=debug_report_md,
            config=config or {},
        )
    except Exception:
        return None


def _export_corpus_case_inner(
    run_state: Dict[str, Any],
    *,
    corpus_root: str,
    reader_report_md: Optional[str],
    debug_report_md: Optional[str],
    config: Dict[str, Any],
) -> str:
    """Inner implementation — may raise on I/O errors."""
    article = _sd(run_state.get("article"))
    genre = _resolve_genre(run_state)
    year, month = _derive_year_month(article)
    case_folder = _derive_case_folder_name(article)

    captured_at = _now_iso()
    engine_ver = _engine_version(config)

    # Build case directory path
    case_dir = os.path.join(corpus_root, genre, year, month, case_folder)
    os.makedirs(case_dir, exist_ok=True)

    # 1. article.json
    article_json = _build_article_json(article, engine_ver, captured_at)
    with open(os.path.join(case_dir, "article.json"), "w", encoding="utf-8") as f:
        json.dump(article_json, f, indent=2, ensure_ascii=False)

    # 2. run.json — raw structured output, no mutation
    with open(os.path.join(case_dir, "run.json"), "w", encoding="utf-8") as f:
        json.dump(run_state, f, indent=2, ensure_ascii=False, default=str)

    # 3. reader_review.md
    reader_text = reader_report_md or "# Reader Review\n\n*Report not yet available.*\n"
    with open(os.path.join(case_dir, "reader_review.md"), "w", encoding="utf-8") as f:
        f.write(reader_text)

    # 4. scholar_debug.md
    debug_text = debug_report_md or "# Scholar Debug Report\n\n*Report not yet available.*\n"
    with open(os.path.join(case_dir, "scholar_debug.md"), "w", encoding="utf-8") as f:
        f.write(debug_text)

    # Update manifest
    manifest_path = os.path.join(corpus_root, "manifest.json")
    entries = _load_manifest(manifest_path)

    # Deduplicate by fingerprint
    fp = article_json.get("fingerprint")
    if fp:
        entries = [e for e in entries if e.get("fingerprint") != fp]

    rel_path = os.path.relpath(case_dir, corpus_root)
    entry = _manifest_entry(case_folder, rel_path, article_json)
    entries.append(entry)
    _save_manifest(manifest_path, entries)

    return case_dir
