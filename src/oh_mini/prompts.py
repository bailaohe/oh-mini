"""Coding-agent system prompt with cwd injection."""

from __future__ import annotations

import os

from meta_harney.builtin.prompt.minimal import MinimalPromptBuilder


class CodingPromptBuilder(MinimalPromptBuilder):  # type: ignore[misc]
    """Wraps the base MinimalPromptBuilder with a coding-agent persona."""

    async def build_system_prompt(self, session_id: str) -> str:
        base = await super().build_system_prompt(session_id)
        cwd = os.getcwd()
        persona = (
            f"You are a coding assistant operating in directory: {cwd}\n\n"
            "Use the available tools to read code, modify files, run commands, "
            "and verify your work. When unsure, prefer reading files first. "
            "Always run tests after non-trivial changes. Use the TodoWrite tool "
            "to plan multi-step work."
        )
        if not base:
            return persona
        return f"{persona}\n\n{base}"
