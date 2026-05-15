"""Coding-agent system prompt with tool-identity anchor + cwd injection.

Why an identity anchor (the `IMPORTANT:` block) and not just plain
persona text:

When tools are attached to a request, some models (notably DeepSeek's
deepseek-v4-pro reasoning model) default to claiming Claude identity —
verified at the curl/HTTP level, 5/5 across runs. Anchoring identity to
the tool name (oh-mini) rather than any specific model keeps the brand
stable across providers and suppresses the drift. Pattern modeled on
OpenHarness's `_BASE_SYSTEM_PROMPT`.
"""

from __future__ import annotations

import os

from meta_harney.builtin.prompt.minimal import MinimalPromptBuilder

_IDENTITY_PROMPT = """\
You are oh-mini, an open-source AI coding assistant CLI. You are an \
interactive agent that helps users with software engineering tasks. Use \
the instructions below and the tools available to you to assist the user.

IMPORTANT: Your identity is oh-mini, regardless of the underlying \
inference engine that powers you (which may be Claude, GPT, DeepSeek, \
Gemini, or another model). When asked who you are, identify as oh-mini. \
Never claim to be Claude, GPT, DeepSeek, or any other model name."""


class CodingPromptBuilder(MinimalPromptBuilder):  # type: ignore[misc]
    """Wraps the base MinimalPromptBuilder with oh-mini's coding-agent
    persona.

    Identity is intentionally model-agnostic — we anchor on the tool name
    (oh-mini) rather than the underlying LLM. Mirrors OpenHarness's
    `_BASE_SYSTEM_PROMPT` (see openharness/prompts/system_prompt.py).
    """

    async def build_system_prompt(self, session_id: str) -> str:
        base = await super().build_system_prompt(session_id)
        cwd = os.getcwd()
        persona = (
            f"{_IDENTITY_PROMPT}\n\n"
            f"Operating in directory: {cwd}\n\n"
            "Use the available tools to read code, modify files, run "
            "commands, and verify your work. When unsure, prefer reading "
            "files first. Always run tests after non-trivial changes. "
            "Use the TodoWrite tool to plan multi-step work."
        )
        if not base:
            return persona
        return f"{persona}\n\n{base}"
