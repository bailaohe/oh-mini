"""FileWriteTool — create or overwrite a text file."""
from __future__ import annotations

from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel

from oh_mini.tools._safety import PathOutsideCwdError, resolve_path_within_cwd


class _FileWriteInput(BaseModel):
    path: str
    content: str


class FileWriteTool(BaseTool):  # type: ignore[misc]
    name = "file_write"
    description = "Create or overwrite a text file at `path` with `content`."
    input_schema = _FileWriteInput

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        try:
            path = resolve_path_within_cwd(inv.args["path"])
        except PathOutsideCwdError as exc:
            return ToolResult(success=False, error=str(exc))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(inv.args["content"], encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, error=f"write failed: {exc}")
        return ToolResult(success=True, output=f"wrote {len(inv.args['content'])} bytes to {path}")
