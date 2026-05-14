"""Tests for CredentialResolver."""

from __future__ import annotations

import pytest

from oh_mini.auth.resolver import CredentialResolver, NoCredentialError
from oh_mini.auth.storage import CredentialKey


class _InMemoryBackend:
    """Test fixture: dict-backed Backend implementing CredentialBackend Protocol."""

    def __init__(self, data: dict[CredentialKey, str] | None = None) -> None:
        self._d = dict(data or {})
        self._ts: dict[CredentialKey, float] = {}

    def get(self, key: CredentialKey) -> str | None:
        return self._d.get(key)

    def put(self, key: CredentialKey, secret: str) -> None:
        self._d[key] = secret

    def delete(self, key: CredentialKey) -> bool:
        self._ts.pop(key, None)
        return self._d.pop(key, None) is not None

    def list(self) -> list[CredentialKey]:
        return list(self._d.keys())

    def touch(self, key: CredentialKey) -> None:
        if key in self._d:
            self._ts[key] = 0.0

    def get_last_used(self, key: CredentialKey) -> float:
        return self._ts.get(key, 0.0)


def test_resolver_cli_api_key_wins(monkeypatch):
    backend = _InMemoryBackend({CredentialKey("deepseek"): "sk-storage"})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env")
    r = CredentialResolver(backend)
    assert r.resolve("deepseek", cli_api_key="sk-cli") == "sk-cli"


def test_resolver_env_beats_storage(monkeypatch):
    backend = _InMemoryBackend({CredentialKey("deepseek"): "sk-storage"})
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env")
    r = CredentialResolver(backend)
    assert r.resolve("deepseek") == "sk-env"


def test_resolver_storage_when_no_cli_no_env(monkeypatch):
    backend = _InMemoryBackend({CredentialKey("deepseek"): "sk-storage"})
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    r = CredentialResolver(backend)
    assert r.resolve("deepseek") == "sk-storage"


def test_resolver_no_credential_raises(monkeypatch):
    backend = _InMemoryBackend()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    r = CredentialResolver(backend)
    with pytest.raises(NoCredentialError) as exc:
        r.resolve("deepseek")
    assert exc.value.provider == "deepseek"
    assert exc.value.profile == "default"


def test_resolver_profile_separates_credentials(monkeypatch):
    backend = _InMemoryBackend(
        {
            CredentialKey("deepseek", "default"): "sk-default",
            CredentialKey("deepseek", "work"): "sk-work",
        }
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    r = CredentialResolver(backend)
    assert r.resolve("deepseek", "default") == "sk-default"
    assert r.resolve("deepseek", "work") == "sk-work"
