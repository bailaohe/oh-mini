"""Tests for NotebookEditTool."""

from __future__ import annotations

import nbformat
from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.notebook_edit import NotebookEditTool


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="notebook_edit", args=args, invocation_id="t1", session_id="s1")


def _write_nb(path, cells_sources):
    nb = nbformat.v4.new_notebook()
    nb["cells"] = [nbformat.v4.new_code_cell(s) for s in cells_sources]
    nbformat.write(nb, path)


async def test_edit_cell_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    nb_path = tmp_path / "x.ipynb"
    _write_nb(nb_path, ["print('hi')", "print('old')"])
    inv = _make_inv({"path": "x.ipynb", "cell_index": 1, "new_source": "print('new')"})
    result = await NotebookEditTool().execute(inv, _make_ctx())
    assert result.success
    nb = nbformat.read(nb_path, as_version=4)
    assert nb["cells"][1]["source"] == "print('new')"


async def test_cell_index_out_of_range_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    nb_path = tmp_path / "x.ipynb"
    _write_nb(nb_path, ["only one cell"])
    inv = _make_inv({"path": "x.ipynb", "cell_index": 5, "new_source": "..."})
    result = await NotebookEditTool().execute(inv, _make_ctx())
    assert not result.success
    assert "index" in (result.error or "").lower()


async def test_non_ipynb_file_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "not-a-notebook.txt"
    p.write_text("hello")
    inv = _make_inv({"path": "not-a-notebook.txt", "cell_index": 0, "new_source": "..."})
    result = await NotebookEditTool().execute(inv, _make_ctx())
    assert not result.success
