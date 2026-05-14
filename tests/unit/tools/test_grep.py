"""Tests for GrepTool."""
from __future__ import annotations

from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.grep import GrepTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="grep", args=args, invocation_id="t1", session_id="s1")


async def test_grep_finds_pattern(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("hello world\n")
    (tmp_path / "b.py").write_text("goodbye\n")
    inv = _make_inv({"pattern": "hello"})
    result = await GrepTool().execute(inv, _make_ctx())
    assert result.success
    out = str(result.output)
    assert "a.py" in out
    assert "hello" in out
    assert "b.py" not in out


async def test_grep_no_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("hello\n")
    inv = _make_inv({"pattern": "nonexistent_xyz"})
    result = await GrepTool().execute(inv, _make_ctx())
    assert result.success
    s = str(result.output)
    assert "no matches" in s.lower() or s.strip() == ""


async def test_grep_filters_by_glob(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("hello\n")
    (tmp_path / "a.txt").write_text("hello\n")
    inv = _make_inv({"pattern": "hello", "glob": "*.py"})
    result = await GrepTool().execute(inv, _make_ctx())
    assert result.success
    out = str(result.output)
    assert "a.py" in out
    assert "a.txt" not in out


async def test_grep_max_matches_truncates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("hit\n")
    inv = _make_inv({"pattern": "hit", "max_matches": 2})
    result = await GrepTool().execute(inv, _make_ctx())
    assert result.success
    out = str(result.output)
    hit_count = sum(out.count(f"f{i}.py") for i in range(5))
    assert hit_count <= 2
