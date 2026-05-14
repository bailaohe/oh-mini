"""Interactive REPL loop."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from meta_harney.abstractions._types import Message, TextBlock
from rich.console import Console

from oh_mini.output import render_stream_event
from oh_mini.runtime import build_runtime


async def run_repl(args: argparse.Namespace) -> int:
    # TTY check (bypass if test env var set)
    if not sys.stdin.isatty() and os.environ.get("OH_MINI_TEST_REPL_FORCE") != "1":
        sys.stderr.write("error: REPL requires a TTY (or set OH_MINI_TEST_REPL_FORCE=1)\n")
        return 1

    sessions_root = Path(args.sessions_root) if args.sessions_root else None
    yolo: bool = args.yolo
    if args.no_yolo:
        yolo = False
    rt = build_runtime(
        provider=args.provider, model=args.model, yolo=yolo,
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
    console.print(f"[bold cyan]oh-mini[/] · Session: {session.id}")
    console.print("[dim]/exit, /quit  exit · /clear  new session · /sessions  list[/]")

    while True:
        try:
            line = input("oh> ")
        except (EOFError, KeyboardInterrupt):
            console.print("\nbye")
            return 0
        line = line.strip()
        if not line:
            continue
        if line in {"/exit", "/quit"}:
            console.print("bye")
            return 0
        if line == "/clear":
            session = await rt.create_session()
            console.print(f"[dim]new Session: {session.id}[/]")
            continue
        if line == "/sessions":
            ids = await rt._session_store.list()
            for s in ids:
                console.print(f"  {s.id}  created {s.created_at}")
            continue
        try:
            user_msg = Message(role="user", content=[TextBlock(text=line)])
            async for ev in rt.stream(session.id, user_msg):
                render_stream_event(ev, console, show_thinking=args.show_thinking)
            console.print()
        except Exception as exc:
            console.print(f"\n[red]error:[/] {exc}")
