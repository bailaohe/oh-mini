"""NotebookEditTool — edit a single code cell of a Jupyter notebook."""
from __future__ import annotations

import nbformat
from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel, Field

from oh_mini.tools._safety import PathOutsideCwdError, resolve_path_within_cwd


class _NotebookEditInput(BaseModel):
    path: str
    cell_index: int = Field(ge=0)
    new_source: str


class NotebookEditTool(BaseTool):  # type: ignore[misc]
    name = "notebook_edit"
    description = (
        "Replace the source of a single cell in a Jupyter notebook (.ipynb). "
        "cell_index is 0-based."
    )
    input_schema = _NotebookEditInput

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        try:
            path = resolve_path_within_cwd(str(inv.args["path"]))
        except PathOutsideCwdError as exc:
            return ToolResult(success=False, error=str(exc))
        if not path.exists():
            return ToolResult(success=False, error=f"no such file: {inv.args['path']}")
        if path.suffix != ".ipynb":
            return ToolResult(success=False, error=f"not a notebook (.ipynb): {path}")
        try:
            nb = nbformat.read(str(path), as_version=4)  # type: ignore[no-untyped-call]
        except Exception as exc:
            return ToolResult(success=False, error=f"notebook read failed: {exc}")
        cell_index = int(inv.args["cell_index"])
        if cell_index < 0 or cell_index >= len(nb["cells"]):
            return ToolResult(
                success=False,
                error=(
                    f"cell_index {cell_index} out of range "
                    f"(notebook has {len(nb['cells'])} cells)"
                ),
            )
        nb["cells"][cell_index]["source"] = str(inv.args["new_source"])
        try:
            nbformat.write(nb, str(path))  # type: ignore[no-untyped-call]
        except Exception as exc:
            return ToolResult(success=False, error=f"notebook write failed: {exc}")
        return ToolResult(success=True, output=f"edited cell {cell_index} of {path}")
