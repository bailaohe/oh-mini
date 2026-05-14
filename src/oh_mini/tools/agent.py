"""AgentTool — spawn a read-only sub-agent via meta-harney MultiAgentBackend."""

from __future__ import annotations

from meta_harney.abstractions._types import TextBlock
from meta_harney.abstractions.multi_agent import AgentSpec
from meta_harney.abstractions.tool import BaseTool, ToolContext, ToolInvocation, ToolResult
from pydantic import BaseModel

SUBAGENT_ALLOWED_TOOLS: list[str] = ["file_read", "grep", "glob"]


class _AgentInput(BaseModel):
    description: str
    prompt: str


class AgentTool(BaseTool):  # type: ignore[misc]
    name = "agent"
    description = (
        "Spawn a sub-agent to research and report back. The sub-agent has access "
        "only to read-only tools (file_read, grep, glob). Returns the sub-agent's "
        "final assistant message text."
    )
    input_schema = _AgentInput

    async def execute(
        self,
        inv: ToolInvocation,
        ctx: ToolContext,
    ) -> ToolResult:
        if ctx.multi_agent is None:
            return ToolResult(success=False, error="multi-agent backend not configured")
        spec = AgentSpec(
            name="sub-agent",
            instructions=str(inv.args["prompt"]),
            allowed_tools=list(SUBAGENT_ALLOWED_TOOLS),
            max_iters=5,
        )
        try:
            handle = await ctx.multi_agent.spawn(
                spec,
                str(inv.args["prompt"]),
                inv.session_id,
                mode="blocking",
            )
            result_msg = await ctx.multi_agent.join(handle.child_session_id)
        except Exception as exc:
            return ToolResult(success=False, error=f"sub-agent failed: {exc}")
        text_parts: list[str] = []
        for block in result_msg.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
        return ToolResult(success=True, output="\n".join(text_parts) or "(empty response)")
