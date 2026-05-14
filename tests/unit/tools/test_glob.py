"""Tests for GlobTool."""
from __future__ import annotations

from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.glob import GlobTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="glob", args=args, invocation_id="t1", session_id="s1")


async def test_glob_finds_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    inv = _make_inv({"pattern": "*.py"})
    result = await GlobTool().execute(inv, _make_ctx())
    assert result.success
    out = str(result.output)
    assert "a.py" in out
    assert "b.py" in out
    assert "c.txt" not in out


async def test_glob_no_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.txt").write_text("")
    inv = _make_inv({"pattern": "*.nonexistent"})
    result = await GlobTool().execute(inv, _make_ctx())
    assert result.success
    s = str(result.output)
    assert "no matches" in s.lower() or s.strip() == ""


async def test_glob_recursive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.py").write_text("")
    (tmp_path / "top.py").write_text("")
    inv = _make_inv({"pattern": "**/*.py"})
    result = await GlobTool().execute(inv, _make_ctx())
    assert result.success
    out = str(result.output)
    assert "deep.py" in out
    assert "top.py" in out
