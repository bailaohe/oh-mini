"""GlobTool — match files by glob pattern."""

from __future__ import annotations

from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel

from oh_mini.tools._safety import PathOutsideCwdError, resolve_path_within_cwd


class _GlobInput(BaseModel):
    pattern: str
    path: str = "."


class GlobTool(BaseTool):  # type: ignore[misc]
    name = "glob"
    description = "Match file paths by glob pattern (supports `**` recursion)."
    input_schema = _GlobInput

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        try:
            root = resolve_path_within_cwd(str(inv.args.get("path", ".")))
        except PathOutsideCwdError as exc:
            return ToolResult(success=False, error=str(exc))
        pattern = str(inv.args["pattern"])
        try:
            matches = sorted(root.glob(pattern))
        except (OSError, ValueError) as exc:
            return ToolResult(success=False, error=f"glob failed: {exc}")
        if not matches:
            return ToolResult(success=True, output="no matches")
        rels = [str(p.relative_to(root)) for p in matches]
        return ToolResult(success=True, output="\n".join(rels))
