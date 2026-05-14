"""Credential storage backends.

KeyringBackend uses the system keyring (macOS Keychain, Linux Secret
Service, Windows Credential Manager). FileBackend stores plain-text
JSON at ~/.oh-mini/credentials.json with POSIX mode 0600.

default_backend() probes keyring availability and falls back to file.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import keyring


@dataclass(frozen=True)
class CredentialKey:
    provider: str
    profile: str = "default"


class CredentialStorageError(Exception):
    """Raised on backend I/O failures (corrupted file, keyring crash)."""


class CredentialBackend(Protocol):
    def get(self, key: CredentialKey) -> str | None: ...
    def put(self, key: CredentialKey, secret: str) -> None: ...
    def delete(self, key: CredentialKey) -> bool: ...
    def list(self) -> list[CredentialKey]: ...
    def touch(self, key: CredentialKey) -> None: ...
    def get_last_used(self, key: CredentialKey) -> float: ...


# --------------------------------------------------------------------------- #
# FileBackend
# --------------------------------------------------------------------------- #


_CredEntry = dict[str, float | str]  # {"secret": str, "last_used": float}
_CredStore = dict[str, dict[str, _CredEntry]]


class FileBackend:
    """JSON v2 storage:
        {
          "version": 2,
          "credentials": {
            "<provider>": {
              "<profile>": {"secret": "<api_key>", "last_used": 1715731200.0}
            }
          }
        }

    Lazy-reads v1 (secret as bare string, last_used=0.0).
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def _load(self) -> _CredStore:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CredentialStorageError(
                f"credentials file corrupted: {self._path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise CredentialStorageError(f"credentials file has unexpected schema: {self._path}")
        version = data.get("version")
        if version not in (1, 2):
            raise CredentialStorageError(
                f"credentials file has unexpected version {version!r}: {self._path}"
            )
        creds_raw = data.get("credentials", {})
        if not isinstance(creds_raw, dict):
            raise CredentialStorageError(
                f"credentials file has malformed 'credentials' field: {self._path}"
            )
        return _normalize_creds(creds_raw)

    def _save(self, creds: _CredStore) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        body = json.dumps({"version": 2, "credentials": creds}, indent=2, ensure_ascii=False)
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body + "\n")
        os.replace(tmp, self._path)
        os.chmod(self._path, 0o600)

    def get(self, key: CredentialKey) -> str | None:
        creds = self._load()
        entry = creds.get(key.provider, {}).get(key.profile)
        if entry is None:
            return None
        secret = entry.get("secret")
        return secret if isinstance(secret, str) else None

    def put(self, key: CredentialKey, secret: str) -> None:
        creds = self._load()
        creds.setdefault(key.provider, {})[key.profile] = {
            "secret": secret,
            "last_used": time.time(),
        }
        self._save(creds)

    def delete(self, key: CredentialKey) -> bool:
        creds = self._load()
        if key.provider not in creds or key.profile not in creds[key.provider]:
            return False
        del creds[key.provider][key.profile]
        if not creds[key.provider]:
            del creds[key.provider]
        self._save(creds)
        return True

    def list(self) -> list[CredentialKey]:
        creds = self._load()
        out: list[CredentialKey] = []
        for provider, profiles in creds.items():
            for profile in profiles:
                out.append(CredentialKey(provider, profile))
        return out

    def touch(self, key: CredentialKey) -> None:
        creds = self._load()
        entry = creds.get(key.provider, {}).get(key.profile)
        if entry is None:
            return
        entry["last_used"] = time.time()
        self._save(creds)

    def get_last_used(self, key: CredentialKey) -> float:
        creds = self._load()
        entry = creds.get(key.provider, {}).get(key.profile)
        if entry is None:
            return 0.0
        ts = entry.get("last_used", 0.0)
        return float(ts) if isinstance(ts, (int, float)) else 0.0


def _normalize_creds(creds_raw: dict[str, object]) -> _CredStore:
    """Normalize v1 (bare string secrets) and v2 (entry dicts) into v2 shape in memory."""
    out: _CredStore = {}
    for provider, profiles in creds_raw.items():
        if not isinstance(profiles, dict):
            continue
        out[provider] = {}
        for profile, raw in profiles.items():
            if isinstance(raw, str):
                out[provider][profile] = {"secret": raw, "last_used": 0.0}
            elif isinstance(raw, dict) and "secret" in raw:
                secret = raw["secret"]
                last_used = raw.get("last_used", 0.0)
                out[provider][profile] = {
                    "secret": str(secret),
                    "last_used": float(last_used) if isinstance(last_used, (int, float)) else 0.0,
                }
    return out


# --------------------------------------------------------------------------- #
# KeyringBackend
# --------------------------------------------------------------------------- #

_KEYRING_SERVICE = "oh-mini"


def _username(key: CredentialKey) -> str:
    return f"{key.provider}:{key.profile}"


class KeyringBackend:
    """Uses `keyring` library; sidecar JSON index tracks known keys + last_used.

    Index v2 shape::

        [
          {"provider": "deepseek", "profile": "default", "last_used": 1715731200.0}
        ]

    Old format (list of ``{provider, profile}`` without ``last_used``) is read
    with ``last_used=0.0``, and rewritten in v2 on the next put/touch.
    """

    def __init__(self, *, index_path: Path | None = None) -> None:
        self._index_path = index_path or (Path.home() / ".oh-mini" / "keyring-index.json")

    def _load_index(self) -> dict[tuple[str, str], float]:
        if not self._index_path.exists():
            return {}
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(data, list):
            return {}
        out: dict[tuple[str, str], float] = {}
        for entry in data:
            if not isinstance(entry, dict) or "provider" not in entry:
                continue
            provider = str(entry["provider"])
            profile = str(entry.get("profile", "default"))
            raw_ts = entry.get("last_used", 0.0)
            ts = float(raw_ts) if isinstance(raw_ts, (int, float)) else 0.0
            out[(provider, profile)] = ts
        return out

    def _save_index(self, index: dict[tuple[str, str], float]) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(
            [{"provider": p, "profile": pr, "last_used": ts} for (p, pr), ts in index.items()],
            indent=2,
        )
        self._index_path.write_text(body + "\n", encoding="utf-8")

    def get(self, key: CredentialKey) -> str | None:
        try:
            value = keyring.get_password(_KEYRING_SERVICE, _username(key))
        except Exception as exc:
            raise CredentialStorageError(f"keyring get failed: {exc}") from exc
        return value

    def put(self, key: CredentialKey, secret: str) -> None:
        try:
            keyring.set_password(_KEYRING_SERVICE, _username(key), secret)
        except Exception as exc:
            raise CredentialStorageError(f"keyring put failed: {exc}") from exc
        index = self._load_index()
        index[(key.provider, key.profile)] = time.time()
        self._save_index(index)

    def delete(self, key: CredentialKey) -> bool:
        index = self._load_index()
        if (key.provider, key.profile) not in index:
            return False
        try:
            keyring.delete_password(_KEYRING_SERVICE, _username(key))
        except Exception as exc:
            raise CredentialStorageError(f"keyring delete failed: {exc}") from exc
        del index[(key.provider, key.profile)]
        self._save_index(index)
        return True

    def list(self) -> list[CredentialKey]:
        return [CredentialKey(p, pr) for (p, pr) in self._load_index().keys()]

    def touch(self, key: CredentialKey) -> None:
        index = self._load_index()
        if (key.provider, key.profile) not in index:
            return
        index[(key.provider, key.profile)] = time.time()
        self._save_index(index)

    def get_last_used(self, key: CredentialKey) -> float:
        return self._load_index().get((key.provider, key.profile), 0.0)


# --------------------------------------------------------------------------- #
# Default backend selection
# --------------------------------------------------------------------------- #


_keyring_probe_cached: bool | None = None


def _keyring_available() -> bool:
    """Probe + cache. True if a usable keyring backend is configured."""
    global _keyring_probe_cached
    if _keyring_probe_cached is not None:
        return _keyring_probe_cached
    try:
        kr = keyring.get_keyring()
        backend_name = type(kr).__name__.lower()
        _keyring_probe_cached = "fail" not in backend_name
    except Exception:
        _keyring_probe_cached = False
    return _keyring_probe_cached


def _default_credentials_path() -> Path:
    return Path.home() / ".oh-mini" / "credentials.json"


def default_backend() -> CredentialBackend:
    """Return the best available backend.

    Keyring is preferred; falls back to FileBackend when keyring isn't usable.
    Set OH_MINI_FORCE_FILE_BACKEND=1 to force file backend (for tests).
    """
    if os.environ.get("OH_MINI_FORCE_FILE_BACKEND") == "1":
        return FileBackend(_default_credentials_path())
    if _keyring_available():
        return KeyringBackend()
    return FileBackend(_default_credentials_path())
