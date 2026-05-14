"""GrepTool — recursive pattern search."""
from __future__ import annotations

import fnmatch
import re

from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel, Field

from oh_mini.tools._safety import PathOutsideCwdError, resolve_path_within_cwd


class _GrepInput(BaseModel):
    pattern: str
    path: str = "."
    glob: str | None = None
    max_matches: int = Field(default=100, ge=1)


class GrepTool(BaseTool):  # type: ignore[misc]
    name = "grep"
    description = "Recursive regex search for `pattern` across files. Returns matching lines."
    input_schema = _GrepInput

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
            regex = re.compile(pattern)
        except re.error as exc:
            return ToolResult(success=False, error=f"invalid regex: {exc}")
        glob = inv.args.get("glob")
        max_matches = int(inv.args.get("max_matches", 100))

        matches: list[str] = []
        if root.is_file():
            files = [root]
        else:
            files = [p for p in root.rglob("*") if p.is_file()]
        if glob is not None:
            files = [f for f in files if fnmatch.fnmatch(f.name, str(glob))]
        for f in files:
            try:
                with f.open("r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            rel = f.relative_to(root) if root.is_dir() else f.name
                            matches.append(f"{rel}:{lineno}:{line.rstrip()}")
                            if len(matches) >= max_matches:
                                break
            except OSError:
                continue
            if len(matches) >= max_matches:
                break
        if not matches:
            return ToolResult(success=True, output="no matches")
        return ToolResult(success=True, output="\n".join(matches))
