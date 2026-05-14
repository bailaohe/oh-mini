"""Tests for CredentialResolver."""

from __future__ import annotations

import time

import pytest

from oh_mini.auth.resolver import CredentialResolver, NoCredentialError, pick_default_provider
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


class _RecordingBackend:
    """In-memory backend that records touch() calls."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], tuple[str, float]] = {}
        self.touch_calls: list[CredentialKey] = []

    def get(self, key):
        e = self._store.get((key.provider, key.profile))
        return e[0] if e else None

    def put(self, key, secret):
        self._store[(key.provider, key.profile)] = (secret, time.time())

    def delete(self, key):
        return self._store.pop((key.provider, key.profile), None) is not None

    def list(self):
        return [CredentialKey(p, pr) for (p, pr) in self._store]

    def touch(self, key):
        self.touch_calls.append(key)
        if (key.provider, key.profile) in self._store:
            secret, _ = self._store[(key.provider, key.profile)]
            self._store[(key.provider, key.profile)] = (secret, time.time())

    def get_last_used(self, key):
        e = self._store.get((key.provider, key.profile))
        return e[1] if e else 0.0


def test_resolver_touches_backend_on_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    backend = _RecordingBackend()
    backend.put(CredentialKey("deepseek", "default"), "sk-stored")
    backend.touch_calls.clear()
    resolver = CredentialResolver(backend)
    assert resolver.resolve("deepseek", "default") == "sk-stored"
    assert backend.touch_calls == [CredentialKey("deepseek", "default")]


def test_resolver_does_not_touch_on_cli_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    backend = _RecordingBackend()
    backend.put(CredentialKey("deepseek", "default"), "sk-stored")
    backend.touch_calls.clear()
    resolver = CredentialResolver(backend)
    assert resolver.resolve("deepseek", "default", cli_api_key="sk-cli") == "sk-cli"
    assert backend.touch_calls == []


def test_resolver_does_not_touch_on_env(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _RecordingBackend()
    backend.put(CredentialKey("deepseek", "default"), "sk-stored")
    backend.touch_calls.clear()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env")
    resolver = CredentialResolver(backend)
    assert resolver.resolve("deepseek", "default") == "sk-env"
    assert backend.touch_calls == []


def test_pick_default_provider_zero_credentials_returns_none() -> None:
    backend = _RecordingBackend()
    assert pick_default_provider(backend) is None


def test_pick_default_provider_single_credential_returns_that_provider() -> None:
    backend = _RecordingBackend()
    backend.put(CredentialKey("deepseek", "default"), "sk-1")
    assert pick_default_provider(backend) == "deepseek"


def test_pick_default_provider_multiple_picks_most_recent() -> None:
    backend = _RecordingBackend()
    backend.put(CredentialKey("anthropic", "default"), "sk-a")
    time.sleep(0.01)
    backend.put(CredentialKey("moonshot", "default"), "sk-m")
    time.sleep(0.01)
    backend.put(CredentialKey("deepseek", "default"), "sk-d")
    assert pick_default_provider(backend) == "deepseek"
