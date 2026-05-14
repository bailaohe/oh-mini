"""CLI subcommand handlers for `oh auth ...`."""

from __future__ import annotations

import argparse
import getpass
import sys

from oh_mini.auth.storage import (
    CredentialBackend,
    CredentialKey,
    CredentialStorageError,
    default_backend,
)


def _mask(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 10:
        return "***"
    return f"{secret[:6]}...{secret[-4:]}"


def handle_auth(args: argparse.Namespace) -> int:
    """Dispatch oh auth <login/list/remove/show>."""
    backend = default_backend()
    backend_name = type(backend).__name__

    if args.auth_cmd == "login":
        return _do_login(args, backend, backend_name)
    if args.auth_cmd == "list":
        return _do_list(backend, backend_name)
    if args.auth_cmd == "remove":
        return _do_remove(args, backend, backend_name)
    if args.auth_cmd == "show":
        return _do_show(args, backend, backend_name)
    print(f"error: unknown auth command {args.auth_cmd!r}", file=sys.stderr)
    return 2


def _do_login(args: argparse.Namespace, backend: CredentialBackend, backend_name: str) -> int:
    from meta_harney import BUILT_IN_PROVIDERS

    from oh_mini.config import _default_settings_path, load_settings

    if args.provider not in BUILT_IN_PROVIDERS:
        print(
            f"error: unknown provider {args.provider!r}. Try: oh providers list",
            file=sys.stderr,
        )
        return 2
    profile = args.profile or "default"
    try:
        api_key = getpass.getpass(f"API key for {args.provider} ({profile}): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\naborted", file=sys.stderr)
        return 1
    if not api_key:
        print("error: empty key, aborted", file=sys.stderr)
        return 1
    try:
        backend.put(CredentialKey(args.provider, profile), api_key)
    except CredentialStorageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"saved {args.provider}/{profile} -> {backend_name}")

    # Friendly nudge: did this become the effective default?
    try:
        settings = load_settings(_default_settings_path())
        if settings.default_provider is None:
            keys = backend.list()
            if len(keys) == 1 and keys[0].provider == args.provider:
                print(
                    f'({args.provider} is now your effective default — run `oh "..."` to use it.)'
                )
    except Exception:
        # Never let a nudge failure break the login.
        pass
    return 0


def _do_list(backend: CredentialBackend, backend_name: str) -> int:
    try:
        keys = backend.list()
    except CredentialStorageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not keys:
        print("no credentials stored. Try: oh auth login --provider <name>")
        return 0
    print(f"{'provider':<14} {'profile':<10} {'backend':<16} {'key':<20}")
    for k in sorted(keys, key=lambda x: (x.provider, x.profile)):
        secret = backend.get(k) or ""
        print(f"{k.provider:<14} {k.profile:<10} {backend_name:<16} {_mask(secret):<20}")
    return 0


def _do_remove(args: argparse.Namespace, backend: CredentialBackend, backend_name: str) -> int:
    profile = args.profile or "default"
    try:
        existed = backend.delete(CredentialKey(args.provider, profile))
    except CredentialStorageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if existed:
        print(f"removed {args.provider}/{profile} from {backend_name}")
    else:
        print(f"not found: {args.provider}/{profile}")
    return 0


def _do_show(args: argparse.Namespace, backend: CredentialBackend, backend_name: str) -> int:
    try:
        keys = backend.list()
    except CredentialStorageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    matching = [k for k in keys if k.provider == args.provider]
    if not matching:
        print(f"no credentials for {args.provider}")
        return 0
    for k in matching:
        secret = backend.get(k) or ""
        print(f"  {k.profile:<10} {backend_name:<16} {_mask(secret)}")
    return 0
