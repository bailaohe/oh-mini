"""CLI subcommand handlers for `oh config ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from meta_harney import BUILT_IN_PROVIDERS

from oh_mini.auth.resolver import pick_default_provider
from oh_mini.auth.storage import default_backend
from oh_mini.config import (
    _default_settings_path,
    load_settings,
    unset_setting,
    update_setting,
)

_KNOWN_KEYS = ("default_provider", "default_profile")


def _settings_path() -> Path:
    """Indirection so tests can monkeypatch the settings file location."""
    return _default_settings_path()


def _collect_effective() -> tuple[str | None, str, str]:
    """Return (provider, profile, source) for what would be used right now."""
    s = load_settings(_settings_path())
    profile = s.default_profile
    if s.default_provider is not None:
        return (s.default_provider, profile, "from settings.json")
    try:
        backend = default_backend()
        picked = pick_default_provider(backend)
    except Exception:
        picked = None
    if picked is None:
        return (None, profile, "no credentials stored")
    return (picked, profile, "smart pick (most recently used credential)")


def handle_config(args: argparse.Namespace) -> int:
    """Dispatch `oh config <subcmd>` to the right handler."""
    cmd = args.config_cmd
    if cmd == "set":
        return _do_set(args.key, args.value)
    if cmd == "get":
        return _do_get(args.key)
    if cmd == "show":
        return _do_show()
    if cmd == "unset":
        return _do_unset(args.key)
    print(f"error: unknown config command {cmd!r}", file=sys.stderr)
    return 2


def _check_known_key(key: str) -> bool:
    if key not in _KNOWN_KEYS:
        print(
            f"error: unknown setting {key!r}. Known: {', '.join(_KNOWN_KEYS)}",
            file=sys.stderr,
        )
        return False
    return True


def _do_set(key: str, value: str) -> int:
    if not _check_known_key(key):
        return 2
    if key == "default_provider" and value not in BUILT_IN_PROVIDERS:
        print(
            f"error: unknown provider {value!r}. Try: oh providers list",
            file=sys.stderr,
        )
        return 2
    update_setting(key, value, _settings_path())
    print(f"set {key} = {value}")
    return 0


def _do_get(key: str) -> int:
    if not _check_known_key(key):
        return 2
    s = load_settings(_settings_path())
    value = getattr(s, key)
    if value is None or value == "":
        print(f"{key}: <unset>")
    else:
        print(f"{key}: {value}")
    return 0


def _do_unset(key: str) -> int:
    if not _check_known_key(key):
        return 2
    p = _settings_path()
    s_before = load_settings(p)
    was_set = getattr(s_before, key) is not None and getattr(s_before, key) != ""
    unset_setting(key, p)
    if was_set:
        print(f"unset {key}")
    else:
        print(f"({key} was not set)")
    return 0


def _do_show() -> int:
    p = _settings_path()
    s = load_settings(p)
    file_status = str(p) if p.exists() else f"{p} (not present)"
    print(f"settings file: {file_status}")

    if s.default_provider is None:
        print("default_provider: <unset>")
    else:
        print(f"default_provider: {s.default_provider}            (from settings.json)")
    profile_source = "from settings.json" if p.exists() else "default"
    print(f"default_profile:  {s.default_profile}            ({profile_source})")
    print()
    provider, profile, source = _collect_effective()
    print("effective provider for next `oh ...`:")
    if provider is None:
        print(f"  <none>            ({source})")
        print("  Try: oh auth login --provider <X>")
    else:
        print(f"  {provider}/{profile}            ({source})")
    return 0
