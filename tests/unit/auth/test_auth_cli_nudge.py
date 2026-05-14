"""Unit tests for the post-login nudge in oh auth login."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from oh_mini.auth.cli import handle_auth


def _args(provider: str, profile: str = "default") -> argparse.Namespace:
    return argparse.Namespace(auth_cmd="login", provider=provider, profile=profile)


def test_first_login_prints_nudge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OH_MINI_FORCE_FILE_BACKEND", "1")
    with patch("oh_mini.auth.cli.getpass.getpass", return_value="sk-deepseek-xyz"):
        rc = handle_auth(_args("deepseek"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "deepseek is now your effective default" in out


def test_second_login_does_not_print_nudge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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
