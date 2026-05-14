"""Unit tests for oh config subcommand handler."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from oh_mini.config_cli import handle_config


def _args(**kwargs: Any) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def test_config_set_writes_settings_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="set", key="default_provider", value="deepseek"))
    assert rc == 0
    assert json.loads(p.read_text())["default_provider"] == "deepseek"


def test_config_set_rejects_unknown_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="set", key="bad_key", value="x"))
    assert rc == 2
    captured = capsys.readouterr()
    assert "unknown setting" in captured.err.lower()


def test_config_set_rejects_unknown_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="set", key="default_provider", value="nope-xyz"))
    assert rc == 2
    captured = capsys.readouterr()
    assert "unknown provider" in captured.err.lower()


def test_config_get_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_provider": "moonshot"}), encoding="utf-8")
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="get", key="default_provider"))
    assert rc == 0
    assert "moonshot" in capsys.readouterr().out


def test_config_get_unset_prints_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "settings.json"
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="get", key="default_provider"))
    assert rc == 0
    assert "unset" in capsys.readouterr().out.lower()


def test_config_unset_removes_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"default_provider": "deepseek"}), encoding="utf-8")
    monkeypatch.setattr("oh_mini.config_cli._settings_path", lambda: p)
    rc = handle_config(_args(config_cmd="unset", key="default_provider"))
    assert rc == 0
    raw = json.loads(p.read_text())
    assert "default_provider" not in raw


def test_config_show_outputs_effective_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
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
