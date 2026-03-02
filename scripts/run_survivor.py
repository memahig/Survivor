#!/usr/bin/env python3
"""
FILE: scripts/run_survivor.py
VERSION: 0.2
PURPOSE: CLI entrypoint to run Survivor pipeline on a URL or local text file.

NOTE:
- Adds project root to sys.path so `engine` package is importable when run as a script.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure repo root is on import path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from engine.core.pipeline import run_pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="run_survivor",
        description="Run Survivor end-to-end on an article and write report.md / run.json / tickets.json / debug.md to an output directory.",
    )
    ap.add_argument("--url", default=None, help="Source URL for the article")
    ap.add_argument("--textfile", default=None, help="Local file path containing article text")
    ap.add_argument("--outdir", default="out", help="Output directory (default: out)")
    args = ap.parse_args()

    run_pipeline(url=args.url, textfile=args.textfile, outdir=args.outdir)

    print(f"[survivor] done. outputs written to: {args.outdir}")


if __name__ == "__main__":
    main()