"""FileReadTool — read text files with optional offset/limit."""
from __future__ import annotations

from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel, Field

from oh_mini.tools._safety import PathOutsideCwdError, resolve_path_within_cwd


class _FileReadInput(BaseModel):
    path: str
    offset: int = Field(default=0, ge=0)
    limit: int | None = Field(default=None, ge=1)


class FileReadTool(BaseTool):  # type: ignore[misc]
    name = "file_read"
    description = (
        "Read a text file. Returns its full content, or lines [offset:offset+limit] if specified."
    )
    input_schema = _FileReadInput

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        try:
            path = resolve_path_within_cwd(inv.args["path"])
        except PathOutsideCwdError as exc:
            return ToolResult(success=False, error=str(exc))
        if not path.exists():
            return ToolResult(success=False, error=f"no such file: {inv.args['path']}")
        if path.is_dir():
            return ToolResult(success=False, error=f"path is a directory: {inv.args['path']}")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(success=False, error=f"read failed: {exc}")
        offset = int(inv.args.get("offset", 0))
        limit = inv.args.get("limit")
        if offset or limit is not None:
            lines = text.splitlines(keepends=True)
            if limit is None:
                lines = lines[offset:]
            else:
                lines = lines[offset : offset + int(limit)]
            text = "".join(lines)
        return ToolResult(success=True, output=text)
