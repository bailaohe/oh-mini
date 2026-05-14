"""Tests for FileReadTool."""
from __future__ import annotations

from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.file_read import FileReadTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="file_read", args=args, invocation_id="t1", session_id="s1")


async def test_read_file_happy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "foo.txt"
    p.write_text("line 1\nline 2\nline 3\n")
    inv = _make_inv({"path": "foo.txt"})
    result = await FileReadTool().execute(inv, _make_ctx())
    assert result.success
    assert "line 1" in str(result.output)
    assert "line 3" in str(result.output)


async def test_read_with_offset_and_limit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "foo.txt"
    p.write_text("a\nb\nc\nd\ne\n")
    inv = _make_inv({"path": "foo.txt", "offset": 1, "limit": 2})
    result = await FileReadTool().execute(inv, _make_ctx())
    assert result.success
    assert "b" in str(result.output)
    assert "c" in str(result.output)
    assert "a" not in str(result.output)
    assert "d" not in str(result.output)


async def test_read_missing_file_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"path": "no-such-file.txt"})
    result = await FileReadTool().execute(inv, _make_ctx())
    assert not result.success
    err = (result.error or "").lower()
    assert "no-such-file" in err or "not found" in err or "no such" in err


async def test_read_outside_cwd_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inv = _make_inv({"path": "../etc/passwd"})
    result = await FileReadTool().execute(inv, _make_ctx())
    assert not result.success
    err = (result.error or "").lower()
    assert "outside" in err or "cwd" in err
