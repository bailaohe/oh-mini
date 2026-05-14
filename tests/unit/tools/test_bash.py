"""Tests for BashTool."""
from __future__ import annotations

import sys

import pytest
from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.bash import BashTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="bash", args=args, invocation_id="t1", session_id="s1")


@pytest.mark.skipif(sys.platform == "win32", reason="bash not available on Windows")
async def test_bash_exit_zero_returns_stdout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"command": "echo hello"})
    result = await BashTool().execute(inv, _make_ctx())
    assert result.success
    out = result.output
    assert isinstance(out, dict)
    assert "hello" in str(out["stdout"])
    assert out["exit_code"] == 0


@pytest.mark.skipif(sys.platform == "win32", reason="bash not available on Windows")
async def test_bash_exit_nonzero_still_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"command": "exit 3"})
    result = await BashTool().execute(inv, _make_ctx())
    assert result.success
    assert result.output["exit_code"] == 3


@pytest.mark.skipif(sys.platform == "win32", reason="bash not available on Windows")
async def test_bash_stderr_captured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"command": "echo oops >&2"})
    result = await BashTool().execute(inv, _make_ctx())
    assert result.success
    assert "oops" in str(result.output["stderr"])


@pytest.mark.skipif(sys.platform == "win32", reason="bash not available on Windows")
async def test_bash_timeout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"command": "sleep 5", "timeout": 1})
    result = await BashTool().execute(inv, _make_ctx())
    assert not result.success
    assert "timeout" in (result.error or "").lower()


@pytest.mark.skipif(sys.platform == "win32", reason="bash not available on Windows")
async def test_bash_cwd_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    inv = _make_inv({"command": "pwd", "cwd": str(sub)})
    result = await BashTool().execute(inv, _make_ctx())
    assert result.success
    out_stdout = str(result.output["stdout"])
    assert str(sub) in out_stdout or "sub" in out_stdout
