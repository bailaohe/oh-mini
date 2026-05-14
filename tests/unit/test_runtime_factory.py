"""Tests for build_runtime factory (v0.2.0: consumes meta-harney catalog)."""
from __future__ import annotations

import pytest

from oh_mini.runtime import build_runtime


def test_build_runtime_anthropic(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(
        provider="anthropic", api_key="fake-anth", model="claude-sonnet-4-5", yolo=False
    )
    assert rt is not None
    assert rt._provider is not None


def test_build_runtime_openai(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="openai", api_key="fake-oa", model="gpt-4o", yolo=False)
    assert rt is not None


def test_build_runtime_yolo_flag_propagates(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="anthropic", api_key="fake", model=None, yolo=True)
    assert rt._permission_resolver._yolo is True


def test_build_runtime_loads_all_ten_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="anthropic", api_key="fake", model=None, yolo=False)
    tools = rt._tools
    expected = {
        "file_read", "file_write", "file_edit", "grep", "glob", "bash",
        "todo_write", "agent", "notebook_edit", "web_fetch",
    }
    assert set(tools.keys()) == expected


def test_build_runtime_sessions_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    custom = tmp_path / "custom-sessions"
    build_runtime(
        provider="anthropic", api_key="fake", model=None, yolo=False, sessions_root=custom
    )
    assert custom.exists()


def test_build_runtime_catalog_provider_uses_spec_base_url(monkeypatch, tmp_path):
    """Phase 9b: provider name from catalog → spec.base_url is respected."""
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="moonshot", api_key="sk-moon", model=None, yolo=False)
    assert rt._config.model == "kimi-k2-0905-preview"
    from meta_harney import OpenAIProvider
    assert isinstance(rt._provider, OpenAIProvider)
    assert rt._provider._base_url == "https://api.moonshot.cn/v1"


def test_build_runtime_unknown_provider_exits(monkeypatch, tmp_path):
    """Unknown provider name → sys.exit(2)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit) as exc_info:
        build_runtime(provider="nonexistent-llm", api_key="fake", model=None, yolo=False)
    assert exc_info.value.code == 2
