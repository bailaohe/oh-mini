"""All built-in oh-mini coding tools, indexed by name."""

from __future__ import annotations

from meta_harney.abstractions.tool import BaseTool

from oh_mini.tools.agent import AgentTool
from oh_mini.tools.bash import BashTool
from oh_mini.tools.file_edit import FileEditTool
from oh_mini.tools.file_read import FileReadTool
from oh_mini.tools.file_write import FileWriteTool
from oh_mini.tools.glob import GlobTool
from oh_mini.tools.grep import GrepTool
from oh_mini.tools.notebook_edit import NotebookEditTool
from oh_mini.tools.todo_write import TodoWriteTool
from oh_mini.tools.web_fetch import WebFetchTool


def build_all_tools() -> dict[str, BaseTool]:
    """Construct one instance of each built-in tool, keyed by tool.name."""
    instances: list[BaseTool] = [
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        GrepTool(),
        GlobTool(),
        BashTool(),
        TodoWriteTool(),
        AgentTool(),
        NotebookEditTool(),
        WebFetchTool(),
    ]
    return {t.name: t for t in instances}


__all__ = ["build_all_tools"]
