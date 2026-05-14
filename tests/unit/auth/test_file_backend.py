"""Tests for FileBackend (file-backed credential storage)."""

from __future__ import annotations

import stat

from oh_mini.auth.storage import CredentialKey, FileBackend


def test_file_backend_put_then_get(tmp_path):
    b = FileBackend(tmp_path / "creds.json")
    b.put(CredentialKey("deepseek"), "sk-xxx")
    assert b.get(CredentialKey("deepseek")) == "sk-xxx"


def test_file_backend_writes_mode_0600(tmp_path):
    p = tmp_path / "creds.json"
    b = FileBackend(p)
    b.put(CredentialKey("deepseek"), "sk-xxx")
    mode = stat.S_IMODE(p.stat().st_mode)
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_file_backend_get_missing_returns_none(tmp_path):
    b = FileBackend(tmp_path / "creds.json")
    assert b.get(CredentialKey("deepseek")) is None


def test_file_backend_delete_existing_returns_true_then_gone(tmp_path):
    b = FileBackend(tmp_path / "creds.json")
    b.put(CredentialKey("deepseek"), "sk-x")
    assert b.delete(CredentialKey("deepseek")) is True
    assert b.get(CredentialKey("deepseek")) is None


def test_file_backend_delete_missing_returns_false(tmp_path):
    b = FileBackend(tmp_path / "creds.json")
    assert b.delete(CredentialKey("deepseek")) is False


def test_file_backend_list_returns_all_keys(tmp_path):
    b = FileBackend(tmp_path / "creds.json")
    b.put(CredentialKey("deepseek", "default"), "k1")
    b.put(CredentialKey("deepseek", "work"), "k2")
    b.put(CredentialKey("anthropic"), "k3")
    keys = b.list()
    assert set(keys) == {
        CredentialKey("deepseek", "default"),
        CredentialKey("deepseek", "work"),
        CredentialKey("anthropic", "default"),
    }
