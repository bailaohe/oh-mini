"""Tests for FileWriteTool."""

from __future__ import annotations

from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.file_write import FileWriteTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="file_write", args=args, invocation_id="t1", session_id="s1")


async def test_write_new_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"path": "out.txt", "content": "hello"})
    result = await FileWriteTool().execute(inv, _make_ctx())
    assert result.success
    assert (tmp_path / "out.txt").read_text() == "hello"


async def test_write_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out.txt").write_text("old content")
    inv = _make_inv({"path": "out.txt", "content": "new content"})
    result = await FileWriteTool().execute(inv, _make_ctx())
    assert result.success
    assert (tmp_path / "out.txt").read_text() == "new content"


async def test_write_outside_cwd_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"path": "../escaped.txt", "content": "evil"})
    result = await FileWriteTool().execute(inv, _make_ctx())
    assert not result.success
