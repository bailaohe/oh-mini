"""Tests for CodingPromptBuilder."""

from __future__ import annotations

import os

from meta_harney.builtin.session.memory_store import MemorySessionStore

from oh_mini.prompts import CodingPromptBuilder


async def test_system_prompt_includes_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = MemorySessionStore()
    pb = CodingPromptBuilder(session_store=store)
    prompt = await pb.build_system_prompt("any-session")
    assert str(tmp_path) in prompt or os.fspath(tmp_path) in prompt


async def test_system_prompt_includes_coding_persona(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = MemorySessionStore()
    pb = CodingPromptBuilder(session_store=store)
    prompt = await pb.build_system_prompt("any-session")
    assert "coding assistant" in prompt.lower()
    assert "todowrite" in prompt.lower() or "todo" in prompt.lower()


async def test_system_prompt_anchors_tool_identity(tmp_path, monkeypatch):
    """Identity must be 'oh-mini' regardless of underlying model.

    Required to suppress deepseek-v4-pro's tool-mode default of claiming
    Claude identity — see plans/async-pondering-oasis.md for the 25-run
    empirical evidence.
    """
    monkeypatch.chdir(tmp_path)
    store = MemorySessionStore()
    pb = CodingPromptBuilder(session_store=store)
    prompt = await pb.build_system_prompt("any-session")
    # Tool name appears prominently
    assert "oh-mini" in prompt
    # Explicit IMPORTANT rule covers the three names the model tends to
    # claim — Claude is the primary observed drift, GPT/DeepSeek round it out.
    assert "IMPORTANT" in prompt
    assert "Never claim to be Claude" in prompt
