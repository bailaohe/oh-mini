"""Tests for KeyringBackend (system keyring storage)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from oh_mini.auth.storage import CredentialKey, KeyringBackend


def test_keyring_backend_put_calls_set_password(tmp_path):
    with patch("oh_mini.auth.storage.keyring") as kr:
        b = KeyringBackend(index_path=tmp_path / "index.json")
        b.put(CredentialKey("deepseek", "default"), "sk-xxx")
        kr.set_password.assert_called_once_with("oh-mini", "deepseek:default", "sk-xxx")


def test_keyring_backend_get_returns_keyring_value(tmp_path):
    with patch("oh_mini.auth.storage.keyring") as kr:
        kr.get_password.return_value = "sk-stored"
        b = KeyringBackend(index_path=tmp_path / "index.json")
        result = b.get(CredentialKey("deepseek", "default"))
        assert result == "sk-stored"
        kr.get_password.assert_called_once_with("oh-mini", "deepseek:default")


def test_keyring_backend_get_missing_returns_none(tmp_path):
    with patch("oh_mini.auth.storage.keyring") as kr:
        kr.get_password.return_value = None
        b = KeyringBackend(index_path=tmp_path / "index.json")
        assert b.get(CredentialKey("deepseek", "default")) is None


def test_keyring_backend_delete_existing_returns_true(tmp_path):
    with patch("oh_mini.auth.storage.keyring") as kr:
        b = KeyringBackend(index_path=tmp_path / "index.json")
        b.put(CredentialKey("deepseek"), "sk-x")
        result = b.delete(CredentialKey("deepseek"))
        assert result is True
        kr.delete_password.assert_called_once_with("oh-mini", "deepseek:default")


def test_keyring_backend_list_uses_sidecar_index(tmp_path):
    with patch("oh_mini.auth.storage.keyring"):
        b = KeyringBackend(index_path=tmp_path / "index.json")
        b.put(CredentialKey("deepseek", "default"), "k1")
        b.put(CredentialKey("anthropic", "work"), "k2")
        keys = b.list()
        assert set(keys) == {
            CredentialKey("deepseek", "default"),
            CredentialKey("anthropic", "work"),
        }


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
