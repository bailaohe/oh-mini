"""Render meta-harney StreamEvent into Rich console output."""
from __future__ import annotations

from meta_harney import (
    IterationCompleted,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    ToolCallCompleted,
    ToolCallStarted,
    TurnCompleted,
)
from rich.console import Console


def render_stream_event(
    event: StreamEvent,
    console: Console,
    *,
    show_thinking: bool = False,
) -> None:
    """Render one StreamEvent. Designed to be called inside an async-for loop."""
    if isinstance(event, TextDelta):
        console.out(event.text, end="", highlight=False)
    elif isinstance(event, ThinkingDelta):
        if show_thinking:
            console.out(f"[dim italic]{event.text}[/]", end="", highlight=False)
    elif isinstance(event, ToolCallStarted):
        args_preview = _format_args(event.args)
        console.print(f"\n[cyan]▸ {event.tool_name}[/] {args_preview}")
    elif isinstance(event, ToolCallCompleted):
        if event.result.success:
            console.print(f"  [green]└─ ✓[/] {event.tool_name}")
        else:
            console.print(f"  [red]└─ ✗[/] {event.tool_name}: {event.result.error}")
    elif isinstance(event, IterationCompleted):
        # Engine-internal marker; nothing to show.
        pass
    elif isinstance(event, TurnCompleted):
        console.print(f"\n[dim]done in {event.total_iterations} iters[/]")


def _format_args(args: dict[str, object]) -> str:
    """One-line preview of tool args. Truncate long values."""
    parts: list[str] = []
    for k, v in args.items():
        s = repr(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
