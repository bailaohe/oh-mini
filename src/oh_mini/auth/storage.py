"""Credential storage backends.

KeyringBackend uses the system keyring (macOS Keychain, Linux Secret
Service, Windows Credential Manager). FileBackend stores plain-text
JSON at ~/.oh-mini/credentials.json with POSIX mode 0600.

default_backend() probes keyring availability and falls back to file.
"""
from __future__ import annotations

import json
import os
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


# --------------------------------------------------------------------------- #
# FileBackend
# --------------------------------------------------------------------------- #


class FileBackend:
    """Plain-text JSON storage with POSIX mode 0600.

    JSON shape:
        {
          "version": 1,
          "credentials": {
            "<provider>": {"<profile>": "<api_key>", ...},
            ...
          }
        }
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def _load(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CredentialStorageError(
                f"credentials file corrupted: {self._path}: {exc}"
            ) from exc
        if not isinstance(data, dict) or data.get("version") != 1:
            raise CredentialStorageError(
                f"credentials file has unexpected schema: {self._path}"
            )
        creds = data.get("credentials", {})
        if not isinstance(creds, dict):
            raise CredentialStorageError(
                f"credentials file has malformed 'credentials' field: {self._path}"
            )
        return creds

    def _save(self, creds: dict[str, dict[str, str]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        body = json.dumps(
            {"version": 1, "credentials": creds}, indent=2, ensure_ascii=False
        )
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body + "\n")
        os.replace(tmp, self._path)
        os.chmod(self._path, 0o600)

    def get(self, key: CredentialKey) -> str | None:
        creds = self._load()
        return creds.get(key.provider, {}).get(key.profile)

    def put(self, key: CredentialKey, secret: str) -> None:
        creds = self._load()
        creds.setdefault(key.provider, {})[key.profile] = secret
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


# --------------------------------------------------------------------------- #
# KeyringBackend
# --------------------------------------------------------------------------- #

_KEYRING_SERVICE = "oh-mini"


def _username(key: CredentialKey) -> str:
    return f"{key.provider}:{key.profile}"


class KeyringBackend:
    """Uses `keyring` library. Maintains a sidecar JSON index of stored keys."""

    def __init__(self, *, index_path: Path | None = None) -> None:
        self._index_path = index_path or (
            Path.home() / ".oh-mini" / "keyring-index.json"
        )

    def _load_index(self) -> list[CredentialKey]:
        if not self._index_path.exists():
            return []
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        out: list[CredentialKey] = []
        for entry in data:
            if isinstance(entry, dict) and "provider" in entry:
                out.append(
                    CredentialKey(entry["provider"], entry.get("profile", "default"))
                )
        return out

    def _save_index(self, keys: list[CredentialKey]) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(
            [{"provider": k.provider, "profile": k.profile} for k in keys],
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
        if key not in index:
            index.append(key)
            self._save_index(index)

    def delete(self, key: CredentialKey) -> bool:
        index = self._load_index()
        if key not in index:
            return False
        try:
            keyring.delete_password(_KEYRING_SERVICE, _username(key))
        except Exception as exc:
            raise CredentialStorageError(f"keyring delete failed: {exc}") from exc
        index.remove(key)
        self._save_index(index)
        return True

    def list(self) -> list[CredentialKey]:
        return list(self._load_index())


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
