"""FileEditTool — exact-match string replacement in a file."""

from __future__ import annotations

from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel

from oh_mini.tools._safety import PathOutsideCwdError, resolve_path_within_cwd


class _FileEditInput(BaseModel):
    path: str
    old_string: str
    new_string: str
    replace_all: bool = False


class FileEditTool(BaseTool):  # type: ignore[misc]
    name = "file_edit"
    description = (
        "Exact-match string replacement. `old_string` must occur exactly once "
        "unless `replace_all=true`."
    )
    input_schema = _FileEditInput

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
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(success=False, error=f"read failed: {exc}")
        old = str(inv.args["old_string"])
        new = str(inv.args["new_string"])
        replace_all = bool(inv.args.get("replace_all", False))
        count = content.count(old)
        if count == 0:
            return ToolResult(success=False, error="old_string not found in file")
        if count > 1 and not replace_all:
            return ToolResult(
                success=False,
                error=(
                    f"old_string not unique (found {count} occurrences); "
                    "set replace_all=true or include more context"
                ),
            )
        if replace_all:
            content = content.replace(old, new)
        else:
            content = content.replace(old, new, 1)
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, error=f"write failed: {exc}")
        return ToolResult(
            success=True,
            output=f"replaced {count if replace_all else 1} occurrence(s) in {path}",
        )
