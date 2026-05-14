"""BashTool — run a shell command with timeout."""

from __future__ import annotations

import asyncio

from meta_harney.abstractions.tool import (
    BaseTool,
    ToolContext,
    ToolInvocation,
    ToolResult,
)
from pydantic import BaseModel, Field


class _BashInput(BaseModel):
    command: str
    timeout: int = Field(default=60, ge=1, le=600)
    cwd: str | None = None


class BashTool(BaseTool):  # type: ignore[misc]
    name = "bash"
    description = (
        "Run a bash shell command. Returns stdout, stderr, exit_code. "
        "Non-zero exit is NOT a tool failure (LLM decides). Timeout default 60s."
    )
    input_schema = _BashInput
    default_timeout: float | None = 60.0

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        command = str(inv.args["command"])
        timeout = int(inv.args.get("timeout", 60))
        cwd = inv.args.get("cwd")
        cwd_str = str(cwd) if cwd is not None else None
        try:
            proc = await asyncio.create_subprocess_exec(
                "/bin/bash",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd_str,
            )
        except (OSError, FileNotFoundError) as exc:
            return ToolResult(success=False, error=f"failed to spawn bash: {exc}")
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            return ToolResult(success=False, error=f"timeout after {timeout}s")
        return ToolResult(
            success=True,
            output={
                "stdout": stdout_b.decode("utf-8", errors="replace"),
                "stderr": stderr_b.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode,
            },
        )
