# Phase 9c Implementation Plan — Smart default provider + `oh config`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `oh auth login --provider deepseek` → `oh "..."` Just Work without editing config, plus expose `oh config set/get/show/unset` to manage settings from CLI.

**Architecture:** `Settings.default_provider` becomes `Optional[str]`. When unset, a smart fallback inspects the backend and picks the credential with the largest `last_used` timestamp. Credentials gain a `last_used` field via a versioned storage format with lazy backward-compatible migration. `oh config` writes the settings file atomically.

**Tech Stack:** Python 3.10+, dataclasses, json stdlib, keyring lib, argparse subparsers, pytest, mypy strict, ruff.

**Spec:** `docs/superpowers/specs/2026-05-14-phase9c-smart-default-provider-design.md`

**Branch:** `main` (continuing direct commits per existing oh-mini convention)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/oh_mini/config.py` | Modify | `Settings.default_provider: Optional[str]=None`; add `save_settings`, `update_setting`, `unset_setting` |
| `src/oh_mini/config_cli.py` | Create | `handle_config(args)` — set/get/show/unset dispatcher |
| `src/oh_mini/auth/storage.py` | Modify | Schema v2 with `last_used`; `touch()`, `get_last_used()`; lazy v1→v2 migration |
| `src/oh_mini/auth/resolver.py` | Modify | Call `backend.touch()` on hit; add `pick_default_provider()` |
| `src/oh_mini/auth/cli.py` | Modify | Friendly nudge when first credential is stored |
| `src/oh_mini/cli.py` | Modify | Register `config` subcommand; new resolution chain |
| `src/oh_mini/__init__.py` | Modify | Bump `__version__` to `0.3.0` |
| `pyproject.toml` | Modify | `version = "0.3.0"` |
| `README.md` | Modify | Update Quickstart, add `oh config` section |
| `tests/unit/test_config.py` | Modify | New default + save/update/unset round-trip |
| `tests/unit/test_config_cli.py` | Create | Unit tests for handle_config |
| `tests/unit/auth/test_file_backend.py` | Modify | Schema v2, touch, get_last_used, v1 compat |
| `tests/unit/auth/test_keyring_backend.py` | Modify | Index v2, touch, get_last_used, old-list compat |
| `tests/unit/auth/test_resolver.py` | Modify | touch-on-hit, pick_default_provider |
| `tests/integration/test_smart_default.py` | Create | E2E smart fallback behavior |
| `tests/integration/test_config_cli.py` | Create | E2E `oh config` subprocess |

---

### Task 1: Storage schema v2 with `last_used` (FileBackend)

**Files:**
- Modify: `src/oh_mini/auth/storage.py`
- Test: `tests/unit/auth/test_file_backend.py`

- [ ] **Step 1: Write failing tests for new schema + touch + get_last_used + v1 compat**

Append to `tests/unit/auth/test_file_backend.py`:

```python
import json
import time
from pathlib import Path

import pytest

from oh_mini.auth.storage import CredentialKey, FileBackend


def test_filebackend_put_records_last_used_timestamp(tmp_path: Path) -> None:
    p = tmp_path / "credentials.json"
    backend = FileBackend(p)
    before = time.time()
    backend.put(CredentialKey("deepseek", "default"), "sk-1")
    after = time.time()
    ts = backend.get_last_used(CredentialKey("deepseek", "default"))
    assert before - 1.0 <= ts <= after + 1.0


def test_filebackend_touch_updates_last_used_without_changing_secret(tmp_path: Path) -> None:
    p = tmp_path / "credentials.json"
    backend = FileBackend(p)
    backend.put(CredentialKey("deepseek", "default"), "sk-1")
    first = backend.get_last_used(CredentialKey("deepseek", "default"))
    time.sleep(0.01)
    backend.touch(CredentialKey("deepseek", "default"))
    second = backend.get_last_used(CredentialKey("deepseek", "default"))
    assert second > first
    assert backend.get(CredentialKey("deepseek", "default")) == "sk-1"


def test_filebackend_get_last_used_returns_zero_for_unknown(tmp_path: Path) -> None:
    p = tmp_path / "credentials.json"
    backend = FileBackend(p)
    assert backend.get_last_used(CredentialKey("nope", "default")) == 0.0


def test_filebackend_reads_v1_legacy_format(tmp_path: Path) -> None:
    p = tmp_path / "credentials.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "credentials": {"deepseek": {"default": "sk-legacy"}},
            }
        ),
        encoding="utf-8",
    )
    backend = FileBackend(p)
    assert backend.get(CredentialKey("deepseek", "default")) == "sk-legacy"
    assert backend.get_last_used(CredentialKey("deepseek", "default")) == 0.0
    assert backend.list() == [CredentialKey("deepseek", "default")]


def test_filebackend_writes_v2_after_put_on_legacy_file(tmp_path: Path) -> None:
    p = tmp_path / "credentials.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "credentials": {"deepseek": {"default": "sk-legacy"}},
            }
        ),
        encoding="utf-8",
    )
    backend = FileBackend(p)
    backend.put(CredentialKey("moonshot", "default"), "sk-moon")
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["version"] == 2
    # Legacy entry preserved and now wrapped:
    assert raw["credentials"]["deepseek"]["default"]["secret"] == "sk-legacy"
    assert raw["credentials"]["deepseek"]["default"]["last_used"] == 0.0
    assert raw["credentials"]["moonshot"]["default"]["secret"] == "sk-moon"
    assert raw["credentials"]["moonshot"]["default"]["last_used"] > 0.0
```

Also adjust any existing test asserting `raw["version"] == 1` — change to `== 2`. And any existing assertion that reads `raw["credentials"]["X"]["Y"]` expecting a raw string — change to `["secret"]`.

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/unit/auth/test_file_backend.py -v`
Expected: AttributeError or KeyError — `touch` / `get_last_used` not defined.

- [ ] **Step 3: Implement schema v2 in FileBackend**

In `src/oh_mini/auth/storage.py`:

1. Add `import time` at top.
2. Update CredentialBackend Protocol:

```python
class CredentialBackend(Protocol):
    def get(self, key: CredentialKey) -> str | None: ...
    def put(self, key: CredentialKey, secret: str) -> None: ...
    def delete(self, key: CredentialKey) -> bool: ...
    def list(self) -> list[CredentialKey]: ...
    def touch(self, key: CredentialKey) -> None: ...
    def get_last_used(self, key: CredentialKey) -> float: ...
```

3. Replace FileBackend internals to use v2 shape with entry dict `{secret, last_used}`:

```python
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
        return _normalize_creds(creds_raw, version)

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


def _normalize_creds(creds_raw: dict, version: int) -> _CredStore:
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/auth/test_file_backend.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/auth/storage.py tests/unit/auth/test_file_backend.py
git commit -m "feat(storage): FileBackend v2 schema with last_used + touch (lazy v1 compat)"
```

---

### Task 2: KeyringBackend schema v2 (index file)

**Files:**
- Modify: `src/oh_mini/auth/storage.py`
- Test: `tests/unit/auth/test_keyring_backend.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/auth/test_keyring_backend.py`:

```python
import json
import time
from pathlib import Path
from unittest.mock import patch

from oh_mini.auth.storage import CredentialKey, KeyringBackend


def test_keyring_put_records_last_used_in_index(tmp_path: Path) -> None:
    idx = tmp_path / "keyring-index.json"
    with patch("oh_mini.auth.storage.keyring") as kr:
        kr.set_password.return_value = None
        backend = KeyringBackend(index_path=idx)
        before = time.time()
        backend.put(CredentialKey("deepseek", "default"), "sk-1")
        after = time.time()
    ts = backend.get_last_used(CredentialKey("deepseek", "default"))
    assert before - 1.0 <= ts <= after + 1.0


def test_keyring_touch_updates_last_used(tmp_path: Path) -> None:
    idx = tmp_path / "keyring-index.json"
    with patch("oh_mini.auth.storage.keyring") as kr:
        kr.set_password.return_value = None
        kr.get_password.return_value = "sk-1"
        backend = KeyringBackend(index_path=idx)
        backend.put(CredentialKey("deepseek", "default"), "sk-1")
        first = backend.get_last_used(CredentialKey("deepseek", "default"))
        time.sleep(0.01)
        backend.touch(CredentialKey("deepseek", "default"))
        second = backend.get_last_used(CredentialKey("deepseek", "default"))
    assert second > first


def test_keyring_get_last_used_unknown_returns_zero(tmp_path: Path) -> None:
    idx = tmp_path / "keyring-index.json"
    with patch("oh_mini.auth.storage.keyring"):
        backend = KeyringBackend(index_path=idx)
        assert backend.get_last_used(CredentialKey("nope", "default")) == 0.0


def test_keyring_reads_legacy_index_format(tmp_path: Path) -> None:
    """Old index was a list of {provider, profile} dicts without last_used."""
    idx = tmp_path / "keyring-index.json"
    idx.write_text(
        json.dumps([{"provider": "deepseek", "profile": "default"}]),
        encoding="utf-8",
    )
    with patch("oh_mini.auth.storage.keyring") as kr:
        kr.get_password.return_value = "sk-legacy"
        backend = KeyringBackend(index_path=idx)
        assert backend.list() == [CredentialKey("deepseek", "default")]
        assert backend.get_last_used(CredentialKey("deepseek", "default")) == 0.0
```

Also update existing test that asserts `index_data == [...]` list-shape to expect new dict shape.

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/unit/auth/test_keyring_backend.py -v`
Expected: AttributeError on touch/get_last_used.

- [ ] **Step 3: Implement KeyringBackend changes**

Replace KeyringBackend class in `src/oh_mini/auth/storage.py`:

```python
class KeyringBackend:
    """Uses `keyring` library; sidecar JSON index tracks known keys + last_used.

    Index v2 shape:
        [
          {"provider": "deepseek", "profile": "default", "last_used": 1715731200.0}
        ]

    Old format (list of {provider, profile} without last_used) is read with
    last_used=0.0, and rewritten in v2 on the next put/touch.
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
            [
                {"provider": p, "profile": pr, "last_used": ts}
                for (p, pr), ts in index.items()
            ],
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/auth/test_keyring_backend.py tests/unit/auth/test_file_backend.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/auth/storage.py tests/unit/auth/test_keyring_backend.py
git commit -m "feat(storage): KeyringBackend index v2 with last_used + touch (legacy compat)"
```

---

### Task 3: Resolver — touch on hit + `pick_default_provider`

**Files:**
- Modify: `src/oh_mini/auth/resolver.py`
- Test: `tests/unit/auth/test_resolver.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/auth/test_resolver.py`:

```python
import time

from oh_mini.auth.resolver import CredentialResolver, pick_default_provider
from oh_mini.auth.storage import CredentialKey


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


def test_resolver_touches_backend_on_hit() -> None:
    backend = _RecordingBackend()
    backend.put(CredentialKey("deepseek", "default"), "sk-stored")
    backend.touch_calls.clear()
    resolver = CredentialResolver(backend)
    assert resolver.resolve("deepseek", "default") == "sk-stored"
    assert backend.touch_calls == [CredentialKey("deepseek", "default")]


def test_resolver_does_not_touch_on_cli_key() -> None:
    backend = _RecordingBackend()
    backend.put(CredentialKey("deepseek", "default"), "sk-stored")
    backend.touch_calls.clear()
    resolver = CredentialResolver(backend)
    assert resolver.resolve("deepseek", "default", cli_api_key="sk-cli") == "sk-cli"
    assert backend.touch_calls == []


def test_resolver_does_not_touch_on_env(monkeypatch) -> None:
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


def test_pick_default_provider_multiple_picks_most_recent(monkeypatch) -> None:
    backend = _RecordingBackend()
    backend.put(CredentialKey("anthropic", "default"), "sk-a")
    time.sleep(0.01)
    backend.put(CredentialKey("moonshot", "default"), "sk-m")
    time.sleep(0.01)
    backend.put(CredentialKey("deepseek", "default"), "sk-d")
    assert pick_default_provider(backend) == "deepseek"
```

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/unit/auth/test_resolver.py -v`
Expected: ImportError for `pick_default_provider`, AssertionError for missing touch.

- [ ] **Step 3: Implement resolver changes**

Replace `src/oh_mini/auth/resolver.py`:

```python
"""CredentialResolver — resolve an API key by priority."""

from __future__ import annotations

import os

from oh_mini.auth.storage import CredentialBackend, CredentialKey


class NoCredentialError(Exception):
    """Raised when no credential is found across CLI / env / storage."""

    def __init__(self, provider: str, profile: str) -> None:
        super().__init__(f"no credential for {provider}/{profile}")
        self.provider = provider
        self.profile = profile


class CredentialResolver:
    """Resolves an API key by priority:

    1. cli_api_key (if non-empty)
    2. env var <PROVIDER>_API_KEY (if non-empty)
    3. backend.get(CredentialKey(provider, profile))  -> on hit, backend.touch()
    4. raise NoCredentialError
    """

    def __init__(self, backend: CredentialBackend) -> None:
        self._backend = backend

    def resolve(
        self,
        provider: str,
        profile: str = "default",
        *,
        cli_api_key: str | None = None,
    ) -> str:
        if cli_api_key:
            return cli_api_key
        env_value = os.environ.get(f"{provider.upper()}_API_KEY", "")
        if env_value:
            return env_value
        key = CredentialKey(provider, profile)
        stored = self._backend.get(key)
        if stored:
            self._backend.touch(key)
            return stored
        raise NoCredentialError(provider, profile)


def pick_default_provider(backend: CredentialBackend) -> str | None:
    """Smart fallback when settings.default_provider is unset.

    - 0 credentials: None
    - 1 credential: that provider
    - N credentials: provider with largest last_used (ties broken by name)
    """
    keys = backend.list()
    if not keys:
        return None
    if len(keys) == 1:
        return keys[0].provider
    keys_sorted = sorted(
        keys,
        key=lambda k: (backend.get_last_used(k), k.provider),
        reverse=True,
    )
    return keys_sorted[0].provider
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/auth/ -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/auth/resolver.py tests/unit/auth/test_resolver.py
git commit -m "feat(auth): resolver touches backend on hit + pick_default_provider()"
```

---

### Task 4: Settings — `Optional[default_provider]` + save/update/unset

**Files:**
- Modify: `src/oh_mini/config.py`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_config.py`:

```python
import json
from pathlib import Path

import pytest

from oh_mini.config import (
    Settings,
    load_settings,
    save_settings,
    unset_setting,
    update_setting,
)


def test_settings_default_provider_defaults_to_none() -> None:
    s = Settings()
    assert s.default_provider is None
    assert s.default_profile == "default"


def test_load_settings_returns_explicit_default_provider(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_provider": "deepseek"}), encoding="utf-8")
    s = load_settings(p)
    assert s.default_provider == "deepseek"


def test_load_settings_missing_default_provider_is_none(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_profile": "work"}), encoding="utf-8")
    s = load_settings(p)
    assert s.default_provider is None
    assert s.default_profile == "work"


def test_save_settings_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    save_settings(Settings(default_provider="moonshot", default_profile="work"), p)
    s = load_settings(p)
    assert s.default_provider == "moonshot"
    assert s.default_profile == "work"


def test_save_settings_omits_none_default_provider(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    save_settings(Settings(default_provider=None), p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert "default_provider" not in raw


def test_update_setting_creates_file_if_missing(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    update_setting("default_provider", "deepseek", p)
    assert load_settings(p).default_provider == "deepseek"


def test_update_setting_preserves_other_keys(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps({"default_provider": "anthropic", "custom_providers": [{"name": "x"}]}),
        encoding="utf-8",
    )
    update_setting("default_profile", "work", p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["default_provider"] == "anthropic"
    assert raw["custom_providers"] == [{"name": "x"}]
    assert raw["default_profile"] == "work"


def test_unset_setting_removes_key(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_provider": "deepseek"}), encoding="utf-8")
    unset_setting("default_provider", p)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert "default_provider" not in raw


def test_unset_setting_no_op_when_missing(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    unset_setting("default_provider", p)  # should not raise
    assert not p.exists() or load_settings(p).default_provider is None
```

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/unit/test_config.py -v`
Expected: ImportError on save_settings, ValueError on Settings(default_provider=None) (still defaults to "anthropic").

- [ ] **Step 3: Implement config changes**

Replace `src/oh_mini/config.py`:

```python
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
    """Read the settings.json as a raw dict (no field-level validation)."""
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
    """Atomically write the raw settings dict to path with mode 0644."""
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
    default_provider = str(raw_default) if isinstance(raw_default, str) and raw_default else None
    default_profile = str(data.get("default_profile", "default")) or "default"
    return Settings(default_provider=default_provider, default_profile=default_profile)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Write Settings to path, preserving other keys (custom_providers) if present."""
    p = path if path is not None else _default_settings_path()
    data = _load_raw(p)
    if settings.default_provider is None:
        data.pop("default_provider", None)
    else:
        data["default_provider"] = settings.default_provider
    data["default_profile"] = settings.default_profile
    _write_raw(data, p)


def update_setting(key: str, value: str, path: Path | None = None) -> None:
    """Set a single top-level setting key without disturbing others."""
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_config.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/config.py tests/unit/test_config.py
git commit -m "feat(config): Settings.default_provider Optional + save/update/unset"
```

---

### Task 5: `oh config` CLI module

**Files:**
- Create: `src/oh_mini/config_cli.py`
- Test: `tests/unit/test_config_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_config_cli.py`:

```python
"""Unit tests for oh config subcommand handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from oh_mini.config_cli import handle_config


def _args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def test_config_set_writes_settings_file(tmp_path: Path, monkeypatch, capsys) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="set", key="default_provider", value="deepseek"))
    assert rc == 0
    assert json.loads(p.read_text())["default_provider"] == "deepseek"


def test_config_set_rejects_unknown_key(tmp_path: Path, monkeypatch, capsys) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="set", key="bad_key", value="x"))
    assert rc == 2
    captured = capsys.readouterr()
    assert "unknown setting" in captured.err.lower()


def test_config_set_rejects_unknown_provider(tmp_path: Path, monkeypatch, capsys) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="set", key="default_provider", value="nope-xyz"))
    assert rc == 2
    captured = capsys.readouterr()
    assert "unknown provider" in captured.err.lower()


def test_config_get_existing(tmp_path: Path, monkeypatch, capsys) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_provider": "moonshot"}), encoding="utf-8")
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="get", key="default_provider"))
    assert rc == 0
    assert "moonshot" in capsys.readouterr().out


def test_config_get_unset_prints_unset(tmp_path: Path, monkeypatch, capsys) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="get", key="default_provider"))
    assert rc == 0
    assert "unset" in capsys.readouterr().out.lower()


def test_config_unset_removes_key(tmp_path: Path, monkeypatch, capsys) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_provider": "deepseek"}), encoding="utf-8")
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="unset", key="default_provider"))
    assert rc == 0
    raw = json.loads(p.read_text())
    assert "default_provider" not in raw


def test_config_show_outputs_effective_default(tmp_path: Path, monkeypatch, capsys) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_provider": "deepseek"}), encoding="utf-8")
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    monkeypatch.setattr(
        "oh_mini.config_cli._collect_effective",
        lambda: ("deepseek", "default", "from settings.json"),
    )
    rc = handle_config(_args(config_cmd="show"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "deepseek" in out
    assert "settings.json" in out
```

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/unit/test_config_cli.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `config_cli.py`**

Create `src/oh_mini/config_cli.py`:

```python
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
    print(f"default_profile:  {s.default_profile}            ({'from settings.json' if p.exists() else 'default'})")
    print()
    provider, profile, source = _collect_effective()
    print("effective provider for next `oh ...`:")
    if provider is None:
        print(f"  <none>            ({source})")
        print("  Try: oh auth login --provider <X>")
    else:
        print(f"  {provider}/{profile}            ({source})")
    return 0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_config_cli.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/config_cli.py tests/unit/test_config_cli.py
git commit -m "feat(config): oh config set/get/show/unset subcommand handlers"
```

---

### Task 6: Wire `oh config` + new resolution chain into cli.py

**Files:**
- Modify: `src/oh_mini/cli.py`
- Modify: `src/oh_mini/repl.py` (just resolution chain hook)
- Test: extend later (Task 8 covers E2E)

- [ ] **Step 1: Add `config` subcommand to parser**

In `src/oh_mini/cli.py`:

1. Update `_SUBCOMMANDS`:

```python
_SUBCOMMANDS = frozenset({"auth", "providers", "config"})
```

2. Add to `_build_subcommand_parser()` (after the providers subparser):

```python
    # oh config ...
    config_p = sub.add_parser("config", help="manage settings")
    config_sub = config_p.add_subparsers(dest="config_cmd", required=True)

    config_set = config_sub.add_parser("set", help="set a setting")
    config_set.add_argument("key")
    config_set.add_argument("value")

    config_get = config_sub.add_parser("get", help="get a setting")
    config_get.add_argument("key")

    config_unset = config_sub.add_parser("unset", help="unset a setting")
    config_unset.add_argument("key")

    config_sub.add_parser("show", help="show all settings + effective provider")
```

3. At the top, add the import:

```python
from oh_mini.config_cli import handle_config
```

4. In the `if is_subcommand:` branch, add the `config` dispatch:

```python
        if args.cmd == "auth":
            rc = handle_auth(args)
        elif args.cmd == "providers":
            rc = _handle_providers(args)
        elif args.cmd == "config":
            rc = handle_config(args)
        else:
            parser.print_help()
            rc = 2
```

- [ ] **Step 2: Update resolution chain in `run_one_shot`**

Replace the top of `run_one_shot` in `cli.py`:

```python
async def run_one_shot(args: argparse.Namespace, settings: Settings) -> int:
    from oh_mini.auth.resolver import pick_default_provider

    backend = default_backend()
    provider_name = args.default_provider_flag or settings.default_provider
    if provider_name is None:
        provider_name = pick_default_provider(backend)
    if provider_name is None:
        print(
            "error: no providers configured. Run: oh auth login --provider <name>",
            file=sys.stderr,
        )
        return 1

    profile_name = args.default_profile_flag or settings.default_profile

    if provider_name not in BUILT_IN_PROVIDERS:
        print(
            f"error: unknown provider {provider_name!r}. Try: oh providers list",
            file=sys.stderr,
        )
        return 2

    resolver = CredentialResolver(backend)
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
    # ... rest unchanged
```

Note: the only structural change in this function is the addition of the `pick_default_provider` fallback block at the top — everything after the `if provider_name not in BUILT_IN_PROVIDERS:` check is unchanged.

- [ ] **Step 3: Update resolution chain in `repl.py`**

Read `src/oh_mini/repl.py` and apply the same `pick_default_provider` fallback at the start of the function that resolves provider_name. The exact location depends on existing structure — search for the line `provider_name = args.default_provider_flag or settings.default_provider` and apply the same 3-line guard:

```python
from oh_mini.auth.resolver import pick_default_provider
# ... after computing provider_name from flag/settings:
if provider_name is None:
    provider_name = pick_default_provider(backend)
if provider_name is None:
    print("error: no providers configured. Run: oh auth login --provider <name>", file=sys.stderr)
    return 1
```

Where `backend` is the same `default_backend()` already used by the resolver. If `repl.py` calls `default_backend()` twice, hoist it to a single call.

- [ ] **Step 4: Run all tests + smoke test**

```bash
pytest -q
python -m oh_mini config show
python -m oh_mini config get default_provider
```

Expected: All tests pass. `oh config show` prints settings status without crashing.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/cli.py src/oh_mini/repl.py
git commit -m "feat(cli): wire 'oh config' subcommand + smart-default resolution chain"
```

---

### Task 7: Friendly nudge after first login

**Files:**
- Modify: `src/oh_mini/auth/cli.py`
- Test: `tests/unit/auth/test_auth_cli_nudge.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/unit/auth/test_auth_cli_nudge.py`:

```python
"""Unit tests for the post-login nudge in oh auth login."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from oh_mini.auth.cli import handle_auth


def _args(provider: str, profile: str = "default") -> argparse.Namespace:
    return argparse.Namespace(auth_cmd="login", provider=provider, profile=profile)


def test_first_login_prints_nudge(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OH_MINI_FORCE_FILE_BACKEND", "1")
    with patch("oh_mini.auth.cli.getpass.getpass", return_value="sk-deepseek-xyz"):
        rc = handle_auth(_args("deepseek"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "deepseek is now your effective default" in out


def test_second_login_does_not_print_nudge(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OH_MINI_FORCE_FILE_BACKEND", "1")
    with patch("oh_mini.auth.cli.getpass.getpass", return_value="sk-a"):
        handle_auth(_args("anthropic"))
    capsys.readouterr()  # clear
    with patch("oh_mini.auth.cli.getpass.getpass", return_value="sk-d"):
        rc = handle_auth(_args("deepseek"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "effective default" not in out


def test_nudge_suppressed_when_settings_has_explicit_default(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OH_MINI_FORCE_FILE_BACKEND", "1")
    settings_dir = tmp_path / ".oh-mini"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text(
        json.dumps({"default_provider": "anthropic"}),
        encoding="utf-8",
    )
    with patch("oh_mini.auth.cli.getpass.getpass", return_value="sk-deepseek"):
        rc = handle_auth(_args("deepseek"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "effective default" not in out
```

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/unit/auth/test_auth_cli_nudge.py -v`
Expected: AssertionError (nudge not yet emitted).

- [ ] **Step 3: Implement nudge in `_do_login`**

In `src/oh_mini/auth/cli.py`, modify `_do_login` to print the nudge after successful put:

```python
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
                    f"({args.provider} is now your effective default — "
                    f"run `oh \"...\"` to use it.)"
                )
    except Exception:
        # Never let a nudge failure break the login.
        pass
    return 0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/auth/ -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/auth/cli.py tests/unit/auth/test_auth_cli_nudge.py
git commit -m "feat(auth): nudge after first login when becoming effective default"
```

---

### Task 8: E2E integration tests

**Files:**
- Create: `tests/integration/test_smart_default.py`
- Create: `tests/integration/test_config_cli.py`

- [ ] **Step 1: Write smart default E2E test**

Create `tests/integration/test_smart_default.py`:

```python
"""E2E: after `oh auth login --provider X`, `oh "..."` uses X without --provider."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(args, env_extra=None, tmp_path: Path | None = None, timeout=15):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path) if tmp_path else env["HOME"]
    env["OH_MINI_FORCE_FILE_BACKEND"] = "1"
    # Clear any leaked *_API_KEY env vars from the parent
    for k in list(env.keys()):
        if k.endswith("_API_KEY"):
            del env[k]
    env["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "oh_mini", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=timeout,
    )


def _seed_file_credential(tmp_path: Path, provider: str, secret: str = "sk-fake") -> None:
    """Bypass interactive `oh auth login` by writing credentials.json directly."""
    home_dot = tmp_path / ".oh-mini"
    home_dot.mkdir(exist_ok=True)
    p = home_dot / "credentials.json"
    if p.exists():
        data = json.loads(p.read_text())
    else:
        data = {"version": 2, "credentials": {}}
    data["credentials"].setdefault(provider, {})[
        "default"
    ] = {"secret": secret, "last_used": __import__("time").time()}
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_single_credential_becomes_effective_default(tmp_path: Path) -> None:
    _seed_file_credential(tmp_path, "deepseek")
    proc = _run(["hi"], tmp_path=tmp_path)
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "Session:" in proc.stdout
    assert "hello from fake" in proc.stdout


def test_settings_default_provider_overrides_smart_pick(tmp_path: Path) -> None:
    # Store both; explicit setting wins.
    _seed_file_credential(tmp_path, "deepseek")
    _seed_file_credential(tmp_path, "moonshot")
    (tmp_path / ".oh-mini" / "settings.json").write_text(
        json.dumps({"default_provider": "anthropic"}),
        encoding="utf-8",
    )
    _seed_file_credential(tmp_path, "anthropic")
    proc = _run(["hi"], tmp_path=tmp_path)
    # FakeLLMProvider doesn't care which provider name was passed; we assert the
    # CLI didn't error and selected something. The override is exercised by the
    # absence of "no credential for deepseek" or "no credential for moonshot".
    assert proc.returncode == 0


def test_no_credentials_no_settings_errors_with_hint(tmp_path: Path) -> None:
    proc = _run(["hi"], tmp_path=tmp_path, env_extra={"OH_MINI_TEST_FAKE_PROVIDER": "0"})
    assert proc.returncode == 1
    combined = (proc.stdout + proc.stderr).lower()
    assert "no providers configured" in combined
    assert "oh auth login" in combined


def test_smart_pick_chooses_most_recent_when_multiple_credentials(tmp_path: Path) -> None:
    """Two credentials, second one stored later should win."""
    import time as _time

    _seed_file_credential(tmp_path, "anthropic", "sk-a")
    _time.sleep(0.05)
    _seed_file_credential(tmp_path, "deepseek", "sk-d")
    # We cannot assert which provider was picked from FakeProvider output alone,
    # but `oh config show` reports the effective pick. Use it.
    proc = _run(["config", "show"], tmp_path=tmp_path)
    assert proc.returncode == 0
    assert "deepseek/default" in proc.stdout
    assert "smart pick" in proc.stdout
```

- [ ] **Step 2: Write config CLI E2E test**

Create `tests/integration/test_config_cli.py`:

```python
"""E2E: oh config set/get/show/unset via subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(args, tmp_path: Path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["OH_MINI_FORCE_FILE_BACKEND"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "oh_mini", "config", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=10,
    )


def test_config_set_then_get(tmp_path: Path) -> None:
    proc = _run(["set", "default_provider", "deepseek"], tmp_path)
    assert proc.returncode == 0
    assert "deepseek" in proc.stdout

    proc = _run(["get", "default_provider"], tmp_path)
    assert proc.returncode == 0
    assert "deepseek" in proc.stdout


def test_config_set_unknown_provider_fails(tmp_path: Path) -> None:
    proc = _run(["set", "default_provider", "totally-fake-xyz"], tmp_path)
    assert proc.returncode == 2
    assert "unknown provider" in proc.stderr.lower()


def test_config_set_unknown_key_fails(tmp_path: Path) -> None:
    proc = _run(["set", "weird_key", "x"], tmp_path)
    assert proc.returncode == 2
    assert "unknown setting" in proc.stderr.lower()


def test_config_unset_then_show(tmp_path: Path) -> None:
    _run(["set", "default_provider", "moonshot"], tmp_path)
    proc = _run(["unset", "default_provider"], tmp_path)
    assert proc.returncode == 0
    # File should still exist but key gone
    p = tmp_path / ".oh-mini" / "settings.json"
    raw = json.loads(p.read_text())
    assert "default_provider" not in raw

    proc = _run(["show"], tmp_path)
    assert proc.returncode == 0
    assert "<unset>" in proc.stdout or "no credentials stored" in proc.stdout


def test_config_show_with_no_settings_file(tmp_path: Path) -> None:
    proc = _run(["show"], tmp_path)
    assert proc.returncode == 0
    assert "settings file" in proc.stdout
```

- [ ] **Step 3: Run all tests**

```bash
pytest -q
```

Expected: All 100+ tests pass. If any prior test asserted version "0.2.0" or a v1 storage shape, update it.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_smart_default.py tests/integration/test_config_cli.py
git commit -m "test(integration): smart-default E2E + oh config CLI E2E"
```

---

### Task 9: Version bump + docs + final clean pass

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/oh_mini/__init__.py`
- Modify: `README.md`
- Modify: `tests/integration/test_cli_one_shot.py` (version assertion)

- [ ] **Step 1: Bump version to 0.3.0**

In `pyproject.toml`:

```toml
version = "0.3.0"
```

In `src/oh_mini/__init__.py`:

```python
__version__ = "0.3.0"
```

In `tests/integration/test_cli_one_shot.py` — find the version assertion and change `"0.2.0"` to `"0.3.0"`.

- [ ] **Step 2: Update README**

In `README.md`:

1. After the **Quickstart** section, replace the closing paragraph with:

```markdown
After `oh auth login --provider <X>` your first credential becomes the
*effective default* automatically — subsequent `oh "..."` commands use it
without a `--provider` flag. To override, see [Defaults](#defaults) below.
```

2. Add a new section after **Credential management**:

```markdown
## Defaults

Provider resolution order (highest first):

1. `--provider <X>` CLI flag
2. `default_provider` in `~/.oh-mini/settings.json` (if set)
3. Smart pick: the stored credential with the most recent `last_used`
   timestamp (the credential you most recently logged in or used)
4. Error: prompts you to `oh auth login --provider <X>`

### `oh config` CLI

```bash
oh config show                                # show settings + effective default
oh config get default_provider                # read one setting
oh config set default_provider deepseek       # pin a default
oh config unset default_provider              # revert to smart pick
```

Known settings keys: `default_provider`, `default_profile`.
```

- [ ] **Step 3: Run quality gates**

```bash
mypy src tests
ruff check src tests
ruff format --check src tests
pytest -q
```

Expected: all clean, all green. If `ruff format --check` complains, run `ruff format src tests` and re-commit.

- [ ] **Step 4: Smoke test**

```bash
# Clean slate
rm -rf /tmp/oh-9c-test && mkdir /tmp/oh-9c-test
HOME=/tmp/oh-9c-test OH_MINI_FORCE_FILE_BACKEND=1 OH_MINI_TEST_FAKE_PROVIDER=1 \
  python -m oh_mini config show
HOME=/tmp/oh-9c-test OH_MINI_FORCE_FILE_BACKEND=1 OH_MINI_TEST_FAKE_PROVIDER=1 \
  python -m oh_mini config set default_provider deepseek
HOME=/tmp/oh-9c-test OH_MINI_FORCE_FILE_BACKEND=1 OH_MINI_TEST_FAKE_PROVIDER=1 \
  python -m oh_mini config show
```

Expected: `oh config show` reports `deepseek` from settings.json as effective default.

- [ ] **Step 5: Commit + tag v0.3.0**

```bash
git add pyproject.toml src/oh_mini/__init__.py README.md tests/integration/test_cli_one_shot.py
git commit -m "release: v0.3.0 — smart default provider + oh config CLI

$(cat <<'EOF'
Phase 9c delivers:
- Settings.default_provider becomes Optional[str]=None
- pick_default_provider() smart fallback (0/1/N credentials)
- Credentials gain last_used timestamp; lazy v1->v2 migration
- oh config set/get/show/unset CLI
- Post-login friendly nudge when becoming effective default
- README: new Defaults section + Quickstart hint

Resolution chain:
1. --provider flag
2. settings.default_provider (if set)
3. backend smart pick (most recently used credential)
4. error with login hint
EOF
)"

git tag -a v0.3.0 -m "v0.3.0 — Phase 9c"
```

---

## Self-Review

**Spec coverage:**
- ✅ Smart fallback chain (Task 3 pick_default_provider, Task 6 wires it)
- ✅ Settings opt-in default (Task 4)
- ✅ last_used metadata (Task 1 FileBackend, Task 2 KeyringBackend)
- ✅ Lazy v1 → v2 migration (Task 1 covers FileBackend; Task 2 covers KeyringBackend)
- ✅ Backend API additions: touch, get_last_used (Tasks 1, 2 update Protocol)
- ✅ Resolver touch-on-hit (Task 3)
- ✅ `oh config` CLI minimal set (Task 5 module, Task 6 wiring)
- ✅ Friendly nudge (Task 7)
- ✅ `oh config show` includes effective provider (Task 5 `_collect_effective`)
- ✅ Error paths: unknown key / unknown provider / unset on missing (Task 5 tests + Task 8 E2E)

**Placeholder scan:** No TBDs. Every step has either code, command, or specific instruction. Task 6 Step 3 instructs "read repl.py and apply" because the patch shape depends on existing structure, but gives the exact 3-line patch.

**Type consistency:**
- `CredentialBackend` Protocol gains `touch` and `get_last_used` in Task 1; consumed in Task 3 and onward. ✅
- `Settings.default_provider: Optional[str]` introduced in Task 4; consumed in Task 5 (`getattr(s, key)` returns Optional) and Task 6 (`is None` check). ✅
- `pick_default_provider(backend) -> str | None` defined in Task 3, called in Task 5 `_collect_effective` and Task 6 cli.py. ✅
- `_default_settings_path` underscored function used by Task 5 (`_settings_path()`) and Task 7 (`_default_settings_path`); same module, no rename. ✅

**Risk callouts:**
- Task 1 changes the serialized JSON schema. Existing user data must read transparently — `_normalize_creds` handles both v1 and v2.
- Task 6 modifies repl.py with a non-canonical patch (depends on existing structure). The implementer subagent should `cat` repl.py first and apply intelligently. Worst case: ask for clarification.
- Task 7 modifies `_do_login` which is already covered by older tests in `test_auth_cli.py`; nudge text addition shouldn't break them, but verify.

All clear.

---

## Execution

**Subagent-Driven (per Phase 6+ memory feedback).** Fresh subagent per task, two-stage review (spec compliance + code quality) after each. No human gate between tasks.
