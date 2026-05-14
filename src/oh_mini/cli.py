"""oh-mini CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from meta_harney.abstractions._types import Message, TextBlock
from rich.console import Console

from oh_mini import __version__
from oh_mini.output import render_stream_event
from oh_mini.runtime import build_runtime


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="oh", description="oh-mini coding agent CLI")
    parser.add_argument("prompt", nargs="?", default=None)
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--model", default=None)
    parser.add_argument("--yolo", action="store_true", default=False)
    parser.add_argument("--no-yolo", dest="no_yolo", action="store_true", default=False)
    parser.add_argument("--resume", default=None)
    parser.add_argument("--show-thinking", action="store_true", default=False)
    parser.add_argument("--sessions-root", default=None)
    parser.add_argument("--version", action="version", version=f"oh-mini {__version__}")
    return parser.parse_args(argv)


def _resolve_yolo(args: argparse.Namespace, *, interactive_mode: bool) -> bool:
    """yolo: interactive → False default, one-shot → True default; flags override."""
    if args.yolo:
        return True
    if args.no_yolo:
        return False
    return not interactive_mode


async def run_one_shot(args: argparse.Namespace) -> int:
    sessions_root = Path(args.sessions_root) if args.sessions_root else None
    yolo = _resolve_yolo(args, interactive_mode=False)
    rt = build_runtime(
        provider=args.provider,
        model=args.model,
        yolo=yolo,
        sessions_root=sessions_root,
    )
    console = Console()
    if args.resume:
        session = await rt._session_store.load(args.resume)
        if session is None:
            console.print(f"[red]error:[/] no such session: {args.resume}")
            return 2
    else:
        session = await rt.create_session()
    console.print(f"[dim]Session: {session.id}[/]")
    user_msg = Message(role="user", content=[TextBlock(text=args.prompt)])
    async for ev in rt.stream(session.id, user_msg):
        render_stream_event(ev, console, show_thinking=args.show_thinking)
    console.print(f"\n[dim]Session: {session.id}[/]")
    return 0


async def run_repl(args: argparse.Namespace) -> int:
    """Stub — REPL implemented in Task 18 (oh_mini.repl.run_repl)."""
    from oh_mini.repl import run_repl as _run_repl_inner

    result: int = await _run_repl_inner(args)
    return result


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    interactive = args.prompt is None
    try:
        if interactive:
            rc = asyncio.run(run_repl(args))
        else:
            rc = asyncio.run(run_one_shot(args))
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
