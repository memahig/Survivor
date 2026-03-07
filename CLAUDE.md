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

## Blunt Structural Warning Format

This format exists in two places because it serves two different roles:

### 1. Survivor Manifesto (Doctrine) — `human/survivor_manifesto.md`

Defines the philosophy and canonical wording.

When a persuasion–evidence gap reaches the highest risk level, Survivor issues a direct structural warning:

> This article has the structure of propaganda.
> The argument depends on omitted rival explanations, unsupported causal claims, and escalating existential framing.
> These mechanisms push the reader toward a conclusion before the evidence fully supports it.

**Design Rule:** Survivor names structural patterns directly. No softening with conversational hedging. Explain mechanisms, not author intent.

### 2. Renderer Specification (Implementation) — `engine/render/blunt_report.py`

The renderer comment block enforces the pattern in code:
1. Structural label
2. Mechanism explanation
3. Reader impact

Do NOT soften structural labels with phrases such as: "appears to", "may be", "could be considered".

### Why Both Places

- **Manifesto** defines the philosophy and doctrine
- **Renderer** ensures the code actually outputs it correctly
- Without both, systems drift
