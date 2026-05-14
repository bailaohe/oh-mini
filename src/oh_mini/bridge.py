"""`oh bridge` — run oh-mini as a JSON-RPC bridge server.

Constructs an AgentRuntime with oh-mini's tools + provider catalog +
credentials, wraps in meta-harney's BridgeServer, serves over stdio.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from meta_harney import BUILT_IN_PROVIDERS
from meta_harney.bridge import (
    BridgePermissionResolver,
    BridgeServer,
    BridgeTraceSink,
    ContentLengthFraming,
    Framing,
    NewlineFraming,
)
from meta_harney.builtin.permission.allow_all import AllowAllPermissionResolver

from oh_mini.auth.resolver import (
    CredentialResolver,
    NoCredentialError,
    pick_default_provider,
)
from oh_mini.auth.storage import default_backend
from oh_mini.config import load_settings
from oh_mini.runtime import build_runtime


def _select_framing(name: str) -> Framing:
    if name == "newline":
        return NewlineFraming()
    if name == "content-length":
        return ContentLengthFraming()
    print(
        f"error: unknown framing {name!r}. Choices: newline, content-length",
        file=sys.stderr,
    )
    sys.exit(2)


def _select_permission_resolver(
    *,
    yolo: bool,
    send_request: Callable[[str, dict[str, Any]], Awaitable[Any]] | None,
) -> Any:
    if yolo:
        return AllowAllPermissionResolver()
    assert send_request is not None, "send_request required when yolo=False"
    return BridgePermissionResolver(send_request=send_request)


def handle_bridge(args: argparse.Namespace) -> int:
    """Entry point for `oh bridge`. Returns process exit code."""
    settings = load_settings()
    backend = default_backend()

    # Resolve provider via the same chain as one-shot / REPL:
    # CLI flag > settings > smart pick > error
    provider_name = (
        getattr(args, "provider_flag", None)
        or settings.default_provider
        or pick_default_provider(backend)
    )
    if provider_name is None:
        print(
            "error: no providers configured. Run: oh auth login --provider <name>",
            file=sys.stderr,
        )
        return 1
    if provider_name not in BUILT_IN_PROVIDERS:
        print(
            f"error: unknown provider {provider_name!r}. Try: oh providers list",
            file=sys.stderr,
        )
        return 2

    profile = getattr(args, "profile_flag", None) or settings.default_profile

    resolver = CredentialResolver(backend)
    try:
        api_key = resolver.resolve(
            provider_name, profile, cli_api_key=getattr(args, "api_key", None)
        )
    except NoCredentialError as exc:
        print(
            f"error: {exc}. Try: oh auth login --provider {provider_name}",
            file=sys.stderr,
        )
        return 1

    framing = _select_framing(getattr(args, "framing", "newline"))
    sessions_root = Path(args.sessions_root) if getattr(args, "sessions_root", None) else None

    asyncio.run(
        _run_server(
            provider=provider_name,
            api_key=api_key,
            model=getattr(args, "model", None),
            yolo=bool(getattr(args, "yolo", False)),
            sessions_root=sessions_root,
            framing=framing,
        )
    )
    return 0


async def _run_server(
    *,
    provider: str,
    api_key: str,
    model: str | None,
    yolo: bool,
    sessions_root: Path | None,
    framing: Framing,
) -> None:
    """Wires the BridgeServer with a runtime whose permission resolver +
    trace sink route back through the bridge."""
    # BridgePermissionResolver needs server.send_request, but BridgeServer
    # needs the runtime (which needs the resolver) in __init__. Break the
    # cycle with a holder + lazy callables that resolve once the server is
    # constructed and stored.
    server_holder: dict[str, BridgeServer] = {}

    async def lazy_send_request(method: str, params: dict[str, Any]) -> Any:
        server = server_holder.get("server")
        if server is None:
            raise RuntimeError("bridge server not yet initialized")
        return await server.send_request(method, params)

    async def lazy_send_notification(method: str, params: dict[str, Any]) -> None:
        server = server_holder.get("server")
        if server is None:
            return
        # Server has _send_notification (underscored). We call it directly
        # because BridgeTraceSink needs a notification-emitting callable.
        await server._send_notification(method, params)

    permission = _select_permission_resolver(yolo=yolo, send_request=lazy_send_request)
    trace_sink = BridgeTraceSink(send_notification=lazy_send_notification)

    runtime = build_runtime(
        provider=provider,
        api_key=api_key,
        model=model,
        yolo=False,  # permission_resolver overrides; yolo handled above
        sessions_root=sessions_root,
        permission_resolver=permission,
        trace_sink=trace_sink,
    )

    server = BridgeServer(
        runtime=runtime,
        framing=framing,
        server_info={"name": "oh-mini-bridge", "version": "0.4.0"},
        trace_sink=trace_sink,
    )
    server_holder["server"] = server

    await server.serve_stdio()
