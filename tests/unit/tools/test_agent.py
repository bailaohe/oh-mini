"""Tests for AgentTool."""

from __future__ import annotations

from meta_harney.abstractions._types import Message, TextBlock
from meta_harney.abstractions.multi_agent import AgentSpec, SpawnHandle
from meta_harney.abstractions.task import TaskState
from meta_harney.abstractions.tool import ToolContext, ToolInvocation
from meta_harney.builtin.session.memory_store import MemorySessionStore
from meta_harney.builtin.trace.null_sink import NullSink

from oh_mini.tools.agent import SUBAGENT_ALLOWED_TOOLS, AgentTool


class _StubBackend:
    """Capture spawn args and return a canned final Message."""

    def __init__(self, final_text: str = "sub-agent result") -> None:
        self.captured_spec: AgentSpec | None = None
        self.captured_message: str | None = None
        self._final_text = final_text

    async def spawn(self, spec, initial_message, parent_session_id, *, mode="blocking"):
        self.captured_spec = spec
        self.captured_message = initial_message
        return SpawnHandle(child_session_id="child-1", mode=mode)

    async def join(self, child_session_id, *, timeout=None):
        return Message(role="assistant", content=[TextBlock(text=self._final_text)])

    async def status(self, child_session_id):
        return TaskState.SUCCEEDED

    async def cancel(self, child_session_id):
        return None


def _make_ctx_with_backend(backend: object) -> ToolContext:
    return ToolContext(
        session_store=MemorySessionStore(),
        trace_sink=NullSink(),
        current_span_id="span-1",
        new_span_id=lambda: "span-x",
        multi_agent=backend,
    )


def _make_inv(args: dict[str, object]) -> ToolInvocation:
    return ToolInvocation(name="agent", args=args, invocation_id="t1", session_id="parent")


async def test_agent_blocking_returns_final_text():
    backend = _StubBackend(final_text="42")
    inv = _make_inv({"description": "find the answer", "prompt": "find it"})
    result = await AgentTool().execute(inv, _make_ctx_with_backend(backend))
    assert result.success
    assert "42" in str(result.output)


async def test_agent_subagent_allowed_tools_is_readonly_subset():
    backend = _StubBackend()
    inv = _make_inv({"description": "x", "prompt": "find x"})
    await AgentTool().execute(inv, _make_ctx_with_backend(backend))
    assert backend.captured_spec is not None
    assert set(backend.captured_spec.allowed_tools) == set(SUBAGENT_ALLOWED_TOOLS)
    assert "bash" not in backend.captured_spec.allowed_tools
    assert "file_write" not in backend.captured_spec.allowed_tools
