"""oh-mini configuration (~/.oh-mini/settings.json)."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from meta_harney import ProviderSpec, register_provider


class ConfigError(Exception):
    """Raised on settings.json parse failures."""


@dataclass
class Settings:
    default_provider: str = "anthropic"
    default_profile: str = "default"


def _default_settings_path() -> Path:
    return Path.home() / ".oh-mini" / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    """Read settings.json if it exists; register custom_providers; return Settings.

    Soft-fails on corrupt JSON — warns to stderr and returns defaults.
    """
    p = path if path is not None else _default_settings_path()
    if not p.exists():
        return Settings()

    try:
        data: Any = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"warning: settings file corrupt or unreadable ({p}): {exc}",
            file=sys.stderr,
        )
        return Settings()

    if not isinstance(data, dict):
        print(
            f"warning: settings file top-level is not an object ({p})",
            file=sys.stderr,
        )
        return Settings()

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

    return Settings(
        default_provider=str(data.get("default_provider", "anthropic")),
        default_profile=str(data.get("default_profile", "default")),
    )
