"""Tests for TodoWriteTool."""
from __future__ import annotations

from datetime import datetime, timezone

from meta_harney.abstractions.session import Session
from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.todo_write import TodoWriteTool


async def _make_ctx_with_session(session_id: str) -> ToolContext:
    store = MemorySessionStore()
    await store.save(Session(id=session_id, created_at=datetime.now(timezone.utc)))
    return ToolContext(
        session_store=store,
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=None,
    )


def _make_inv(args: dict[str, object], session_id: str = "s1") -> ToolInvocation:
    return ToolInvocation(name="todo_write", args=args, invocation_id="t1", session_id=session_id)


async def test_todo_write_persists_to_session_attributes():
    ctx = await _make_ctx_with_session("s1")
    todos = [
        {"content": "step 1", "status": "in_progress"},
        {"content": "step 2", "status": "pending"},
    ]
    inv = _make_inv({"todos": todos})
    result = await TodoWriteTool().execute(inv, ctx)
    assert result.success
    session = await ctx.session_store.load("s1")
    assert session is not None
    assert session.attributes["todos"] == todos


async def test_todo_write_overwrites_previous():
    ctx = await _make_ctx_with_session("s1")
    first = [{"content": "old", "status": "pending"}]
    second = [{"content": "new", "status": "completed"}]
    await TodoWriteTool().execute(_make_inv({"todos": first}), ctx)
    await TodoWriteTool().execute(_make_inv({"todos": second}), ctx)
    session = await ctx.session_store.load("s1")
    assert session is not None
    assert session.attributes["todos"] == second
