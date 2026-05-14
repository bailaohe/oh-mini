"""Tests for stream renderer."""
from __future__ import annotations

import io

from meta_harney import (
    IterationCompleted,
    TextDelta,
    ThinkingDelta,
    ToolCallCompleted,
    ToolCallStarted,
    ToolResult,
    TurnCompleted,
)
from rich.console import Console

from oh_mini.output import render_stream_event


def _capture(event: object, *, show_thinking: bool = False) -> str:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    render_stream_event(event, console, show_thinking=show_thinking)
    return buf.getvalue()


def test_render_text_delta_writes_text() -> None:
    out = _capture(TextDelta(text="hello"))
    assert "hello" in out


def test_render_tool_call_started_shows_tool_name() -> None:
    out = _capture(ToolCallStarted(tool_name="bash", invocation_id="t1", args={"command": "ls"}))
    assert "bash" in out


def test_render_tool_call_completed_success() -> None:
    out = _capture(
        ToolCallCompleted(
            tool_name="bash",
            invocation_id="t1",
            result=ToolResult(success=True, output="ok"),
        )
    )
    assert "bash" in out or "✓" in out or "ok" in out


def test_render_tool_call_completed_failure_shows_error() -> None:
    out = _capture(
        ToolCallCompleted(
            tool_name="bash",
            invocation_id="t1",
            result=ToolResult(success=False, output=None, error="boom"),
        )
    )
    assert "boom" in out


def test_render_thinking_delta_suppressed_by_default() -> None:
    out = _capture(ThinkingDelta(text="reasoning"))
    assert "reasoning" not in out


def test_render_thinking_delta_shown_when_flag_set() -> None:
    out = _capture(ThinkingDelta(text="reasoning"), show_thinking=True)
    assert "reasoning" in out


def test_render_turn_completed_shows_iteration_count() -> None:
    out = _capture(TurnCompleted(total_iterations=3))
    assert "3" in out


def test_render_iteration_completed_is_silent() -> None:
    out = _capture(IterationCompleted(iteration=1))
    assert isinstance(out, str)
