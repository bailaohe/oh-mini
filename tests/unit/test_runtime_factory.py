"""Tests for build_runtime factory."""

from __future__ import annotations

from oh_mini.runtime import build_runtime


def test_build_runtime_anthropic(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anth-key")
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="anthropic", model="claude-sonnet-4-5", yolo=False)
    assert rt is not None
    assert rt._provider is not None


def test_build_runtime_openai(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-oa-key")
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="openai", model="gpt-4o", yolo=False)
    assert rt is not None


def test_build_runtime_yolo_flag_propagates(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="anthropic", model=None, yolo=True)
    assert rt._permission_resolver._yolo is True


def test_build_runtime_loads_all_ten_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("HOME", str(tmp_path))
    rt = build_runtime(provider="anthropic", model=None, yolo=False)
    tools = rt._tools
    expected = {
        "file_read",
        "file_write",
        "file_edit",
        "grep",
        "glob",
        "bash",
        "todo_write",
        "agent",
        "notebook_edit",
        "web_fetch",
    }
    assert set(tools.keys()) == expected


def test_build_runtime_sessions_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("HOME", str(tmp_path))
    custom = tmp_path / "custom-sessions"
    build_runtime(provider="anthropic", model=None, yolo=False, sessions_root=custom)
    assert custom.exists()
