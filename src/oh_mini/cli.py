"""oh-mini CLI entry point (Phase 9b: subparser + resolver wiring)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from meta_harney import BUILT_IN_PROVIDERS
from meta_harney.abstractions._types import Message, TextBlock
from rich.console import Console

from oh_mini import __version__
from oh_mini.auth.cli import handle_auth
from oh_mini.auth.resolver import CredentialResolver, NoCredentialError
from oh_mini.auth.storage import default_backend
from oh_mini.config import Settings, load_settings
from oh_mini.output import render_stream_event
from oh_mini.runtime import build_runtime

# Top-level subcommands that take over argument parsing entirely.
_SUBCOMMANDS = frozenset({"auth", "providers"})


def _build_subcommand_parser() -> argparse.ArgumentParser:
    """Parser for `oh auth ...` and `oh providers ...` subcommands."""
    parser = argparse.ArgumentParser(prog="oh", description="oh-mini coding agent CLI")
    parser.add_argument("--version", action="version", version=f"oh-mini {__version__}")

    sub = parser.add_subparsers(dest="cmd", required=False)

    # oh auth ...
    auth_p = sub.add_parser("auth", help="manage credentials")
    auth_sub = auth_p.add_subparsers(dest="auth_cmd", required=True)

    login_p = auth_sub.add_parser("login", help="store a credential")
    login_p.add_argument("--provider", required=True)
    login_p.add_argument("--profile", default="default")

    auth_sub.add_parser("list", help="list stored credentials")

    remove_p = auth_sub.add_parser("remove", help="remove a credential")
    remove_p.add_argument("--provider", required=True)
    remove_p.add_argument("--profile", default="default")

    show_p = auth_sub.add_parser("show", help="show credentials for a provider")
    show_p.add_argument("--provider", required=True)

    # oh providers list
    prov_p = sub.add_parser("providers", help="inspect provider catalog")
    prov_sub = prov_p.add_subparsers(dest="prov_cmd", required=True)
    prov_sub.add_parser("list", help="list known providers")

    return parser


def _build_default_parser() -> argparse.ArgumentParser:
    """Parser for the default `oh [prompt]` / REPL mode."""
    parser = argparse.ArgumentParser(prog="oh", description="oh-mini coding agent CLI")
    parser.add_argument("--version", action="version", version=f"oh-mini {__version__}")
    parser.add_argument("prompt", nargs="?", default=None)
    parser.add_argument("--provider", default=None, dest="default_provider_flag")
    parser.add_argument("--profile", default=None, dest="default_profile_flag")
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None, dest="api_key")
    parser.add_argument("--yolo", action="store_true", default=False)
    parser.add_argument("--no-yolo", dest="no_yolo", action="store_true", default=False)
    parser.add_argument("--resume", default=None)
    parser.add_argument("--show-thinking", action="store_true", default=False)
    parser.add_argument("--sessions-root", default=None)
    return parser


def _resolve_yolo(args: argparse.Namespace, *, interactive_mode: bool) -> bool:
    if args.yolo:
        return True
    if args.no_yolo:
        return False
    return not interactive_mode


async def run_one_shot(args: argparse.Namespace, settings: Settings) -> int:
    provider_name = args.default_provider_flag or settings.default_provider
    profile_name = args.default_profile_flag or settings.default_profile

    if provider_name not in BUILT_IN_PROVIDERS:
        print(
            f"error: unknown provider {provider_name!r}. Try: oh providers list",
            file=sys.stderr,
        )
        return 2

    resolver = CredentialResolver(default_backend())
    try:
        api_key = resolver.resolve(provider_name, profile_name, cli_api_key=args.api_key)
    except NoCredentialError as exc:
        print(
            f"error: {exc}. Try: oh auth login --provider {provider_name}",
            file=sys.stderr,
        )
        return 1

    sessions_root = Path(args.sessions_root) if args.sessions_root else None
    yolo = _resolve_yolo(args, interactive_mode=False)
    rt = build_runtime(
        provider=provider_name,
        api_key=api_key,
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


async def run_repl(args: argparse.Namespace, settings: Settings) -> int:
    from oh_mini.repl import run_repl as _run_repl_inner

    return await _run_repl_inner(args, settings)


def _handle_providers(args: argparse.Namespace) -> int:
    if args.prov_cmd == "list":
        print(f"{'name':<14} {'kind':<10} {'default_model':<28} {'base_url':<55} description")
        for name in sorted(BUILT_IN_PROVIDERS.keys()):
            spec = BUILT_IN_PROVIDERS[name]
            base_url = spec.base_url or "(SDK default)"
            row = (
                f"{name:<14} {spec.kind:<10} {spec.default_model:<28}"
                f" {base_url:<55} {spec.description}"
            )
            print(row)
        return 0
    print(f"error: unknown providers command {args.prov_cmd!r}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> None:
    effective_argv = sys.argv[1:] if argv is None else argv

    # Detect whether first non-flag token is a known subcommand.
    first_positional = next(
        (a for a in effective_argv if not a.startswith("-")), None
    )
    is_subcommand = first_positional in _SUBCOMMANDS

    settings = load_settings()

    if is_subcommand:
        parser = _build_subcommand_parser()
        args = parser.parse_args(effective_argv)
        if args.cmd == "auth":
            rc = handle_auth(args)
        elif args.cmd == "providers":
            rc = _handle_providers(args)
        else:
            parser.print_help()
            rc = 2
    else:
        parser = _build_default_parser()
        args = parser.parse_args(effective_argv)
        interactive = args.prompt is None
        try:
            if interactive:
                rc = asyncio.run(run_repl(args, settings))
            else:
                rc = asyncio.run(run_one_shot(args, settings))
        except KeyboardInterrupt:
            rc = 130

    sys.exit(rc)


if __name__ == "__main__":
    main()
