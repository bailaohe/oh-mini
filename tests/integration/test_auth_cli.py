"""Integration tests for `oh auth ...` subcommands.

Uses OH_MINI_FORCE_FILE_BACKEND=1 to force FileBackend (no keyring side-effects).
Each test runs in an isolated HOME (tmp_path).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _cli_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["OH_MINI_FORCE_FILE_BACKEND"] = "1"
    return env


def test_auth_login_stores_credential(tmp_path: Path) -> None:
    env = _cli_env(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "auth", "login", "--provider", "deepseek"],
        input="sk-deepseek-xxx\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "saved" in proc.stdout
    creds_path = tmp_path / ".oh-mini" / "credentials.json"
    assert creds_path.exists(), f"creds file not at {creds_path}"
    data = json.loads(creds_path.read_text())
    assert data["credentials"]["deepseek"]["default"] == "sk-deepseek-xxx"


def test_auth_login_unknown_provider_exits_2(tmp_path: Path) -> None:
    env = _cli_env(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "auth", "login", "--provider", "nonexistent"],
        input="\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc.returncode == 2
    combined = (proc.stdout + proc.stderr).lower()
    assert "unknown provider" in combined


def test_auth_list_then_remove(tmp_path: Path) -> None:
    env = _cli_env(tmp_path)
    # Login first
    subprocess.run(
        [sys.executable, "-m", "oh_mini", "auth", "login", "--provider", "deepseek"],
        input="sk-x\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    # List
    list_proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "auth", "list"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert list_proc.returncode == 0
    assert "deepseek" in list_proc.stdout
    # Remove
    remove_proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "auth", "remove", "--provider", "deepseek"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert remove_proc.returncode == 0
    assert "removed" in remove_proc.stdout.lower()


def test_auth_remove_idempotent(tmp_path: Path) -> None:
    env = _cli_env(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "auth", "remove", "--provider", "deepseek"],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "not found" in proc.stdout.lower()
