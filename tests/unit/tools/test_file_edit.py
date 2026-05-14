"""Tests for FileEditTool."""
from __future__ import annotations

from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.file_edit import FileEditTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="file_edit", args=args, invocation_id="t1", session_id="s1")


async def test_exact_replace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "foo.py"
    p.write_text("def old():\n    pass\n")
    inv = _make_inv({"path": "foo.py", "old_string": "def old():", "new_string": "def new():"})
    result = await FileEditTool().execute(inv, _make_ctx())
    assert result.success
    assert p.read_text() == "def new():\n    pass\n"


async def test_replace_all_multiple_occurrences(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "foo.py"
    p.write_text("x = 1\ny = 1\nz = 1\n")
    inv = _make_inv({"path": "foo.py", "old_string": "1", "new_string": "2", "replace_all": True})
    result = await FileEditTool().execute(inv, _make_ctx())
    assert result.success
    assert p.read_text() == "x = 2\ny = 2\nz = 2\n"


async def test_old_string_not_found_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "foo.py"
    p.write_text("nothing matches")
    inv = _make_inv({"path": "foo.py", "old_string": "xyz", "new_string": "abc"})
    result = await FileEditTool().execute(inv, _make_ctx())
    assert not result.success
    assert "not found" in (result.error or "").lower()


async def test_non_unique_without_replace_all_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "foo.py"
    p.write_text("x = 1\ny = 1\n")
    inv = _make_inv({"path": "foo.py", "old_string": "1", "new_string": "2"})
    result = await FileEditTool().execute(inv, _make_ctx())
    assert not result.success
    err = (result.error or "").lower()
    assert "unique" in err or "multiple" in err
