"""Tests for FileBackend (file-backed credential storage)."""

from __future__ import annotations

import json
import stat
import time
from pathlib import Path

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
