"""TodoWriteTool — store a todo list in session.attributes."""

from __future__ import annotations

from typing import Literal

from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel


class _TodoItem(BaseModel):
    content: str
    status: Literal["pending", "in_progress", "completed"]


class _TodoWriteInput(BaseModel):
    todos: list[_TodoItem]


class TodoWriteTool(BaseTool):  # type: ignore[misc]
    name = "todo_write"
    description = (
        "Persist a structured todo list in the current session's attributes. "
        "Overwrites any previous list."
    )
    input_schema = _TodoWriteInput

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        session = await ctx.session_store.load(inv.session_id)
        if session is None:
            return ToolResult(success=False, error=f"session {inv.session_id} not found")
        todos = inv.args["todos"]
        normalized: list[dict[str, str]] = []
        for t in todos:
            if isinstance(t, dict):
                normalized.append({"content": str(t["content"]), "status": str(t["status"])})
            else:
                normalized.append({"content": t.content, "status": t.status})
        session.attributes["todos"] = normalized
        try:
            await ctx.session_store.save(session)
        except Exception as exc:
            return ToolResult(success=False, error=f"save failed: {exc}")
        return ToolResult(success=True, output=f"wrote {len(normalized)} todos")
