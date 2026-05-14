"""Tests for KeyringBackend (system keyring storage)."""

from __future__ import annotations

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
