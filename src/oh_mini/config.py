"""oh-mini configuration (~/.oh-mini/settings.json)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from meta_harney import ProviderSpec, register_provider


class ConfigError(Exception):
    """Raised on settings.json parse failures."""


@dataclass
class Settings:
    default_provider: str | None = None
    default_profile: str = "default"


def _default_settings_path() -> Path:
    return Path.home() / ".oh-mini" / "settings.json"


def _load_raw(path: Path) -> dict[str, Any]:
    """Read the settings.json as a raw dict (no field-level validation).

    Soft-fails: missing file / corrupt JSON / non-object → empty dict (with warning).
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"warning: settings file corrupt or unreadable ({path}): {exc}",
            file=sys.stderr,
        )
        return {}
    if not isinstance(data, dict):
        print(
            f"warning: settings file top-level is not an object ({path})",
            file=sys.stderr,
        )
        return {}
    return data


def _write_raw(data: dict[str, Any], path: Path) -> None:
    """Atomically write the raw settings dict to path with mode 0644.

    settings.json is not a secret (unlike credentials.json), so we use 0644.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    body = json.dumps(data, indent=2, ensure_ascii=False)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body + "\n")
    os.replace(tmp, path)


def load_settings(path: Path | None = None) -> Settings:
    """Read settings.json if it exists; register custom_providers; return Settings.

    Soft-fails on corrupt JSON — warns to stderr and returns defaults.
    `default_provider` is Optional[str]; absent / empty / non-string → None.
    """
    p = path if path is not None else _default_settings_path()
    data = _load_raw(p)

    for entry in data.get("custom_providers", []) or []:
        if not isinstance(entry, dict):
            print(
                f"warning: skipping non-object custom_providers entry: {entry!r}",
                file=sys.stderr,
            )
            continue
        try:
            spec = ProviderSpec(
                name=str(entry["name"]),
                kind=entry["kind"],
                base_url=entry.get("base_url"),
                default_model=str(entry["default_model"]),
                description=str(entry.get("description", "")),
            )
            register_provider(spec, overwrite=True)
        except (KeyError, TypeError, ValueError) as exc:
            print(
                f"warning: skipping malformed custom_providers entry "
                f"{entry.get('name', '<no name>')!r}: {exc}",
                file=sys.stderr,
            )

    raw_default = data.get("default_provider")
    default_provider: str | None = (
        str(raw_default) if isinstance(raw_default, str) and raw_default else None
    )
    raw_profile = data.get("default_profile", "default")
    default_profile = str(raw_profile) if raw_profile else "default"
    return Settings(default_provider=default_provider, default_profile=default_profile)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Write Settings to path, preserving other top-level keys (e.g. custom_providers).

    Loads the existing raw dict, overlays the Settings fields, and rewrites.
    `default_provider=None` removes the key from the file.
    """
    p = path if path is not None else _default_settings_path()
    data = _load_raw(p)
    if settings.default_provider is None:
        data.pop("default_provider", None)
    else:
        data["default_provider"] = settings.default_provider
    data["default_profile"] = settings.default_profile
    _write_raw(data, p)


def update_setting(key: str, value: str, path: Path | None = None) -> None:
    """Set a single top-level setting key without disturbing other keys."""
    p = path if path is not None else _default_settings_path()
    data = _load_raw(p)
    data[key] = value
    _write_raw(data, p)


def unset_setting(key: str, path: Path | None = None) -> None:
    """Remove a top-level setting key. No-op if absent or file missing."""
    p = path if path is not None else _default_settings_path()
    if not p.exists():
        return
    data = _load_raw(p)
    if key in data:
        data.pop(key)
        _write_raw(data, p)
