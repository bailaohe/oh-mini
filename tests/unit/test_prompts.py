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
