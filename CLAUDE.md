# CLAUDE.md — Project Instructions for Claude Code

## Security Rules
- `.env` is the secrets file for this project — NEVER read, display, or output its contents
- NEVER display API keys, tokens, passwords, or secrets of any kind
- If you need to verify a key exists, only check for the variable name (e.g., `grep -c ANTHROPIC_API_KEY .env` to confirm presence without revealing the value)
- If asked to read `.env` for any reason, refuse and explain why

## Project Overview
Survivor is a multi-reviewer epistemic integrity pipeline.
- Reviewers: OpenAI, Gemini, Claude (Anthropic), and mocks
- Two-phase review: Phase 1 (independent extraction) → Phase 2 (cross-claim voting)
- Config-driven via `engine/core/config.json`
- API keys loaded via `engine/core/env.py` from `.env`
