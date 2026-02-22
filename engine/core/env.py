#!/usr/bin/env python3
"""
FILE: survivor/core/env.py
VERSION: 0.1
PURPOSE:
Centralized environment variable loader for Survivor.

CONTRACT:
- All API keys must come from .env
- No fallback sources
- Fail closed if missing
"""

import os
from dotenv import load_dotenv


load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_openai_key() -> str:
    return require_env("OPENAI_API_KEY")


def get_gemini_key() -> str:
    return require_env("GEMINI_API_KEY")


def get_claude_key() -> str:
    return require_env("ANTHROPIC_API_KEY")