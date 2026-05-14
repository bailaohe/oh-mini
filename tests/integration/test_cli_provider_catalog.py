"""Integration tests: `oh --provider <name>` routes through the catalog."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    env["OH_MINI_FORCE_FILE_BACKEND"] = "1"
    env.update(extra)
    return env


def test_cli_provider_deepseek_via_env(tmp_path: Path) -> None:
    """--provider deepseek picks up DEEPSEEK_API_KEY env var via resolver."""
    env = _env(tmp_path, DEEPSEEK_API_KEY="sk-fake-deepseek")
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "--provider", "deepseek", "hello"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=15,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "Session:" in proc.stdout
    assert "hello from fake" in proc.stdout


def test_cli_missing_credential_for_provider_exits_1(tmp_path: Path) -> None:
    """Without a stored or env credential, oh exits 1 with login hint."""
    env = _env(tmp_path)
    # Clear any inherited <PROVIDER>_API_KEY env vars
    for k in list(env.keys()):
        if k.endswith("_API_KEY"):
            del env[k]
    # Disable fake-provider short-circuit so build_runtime requires real key
    env["OH_MINI_TEST_FAKE_PROVIDER"] = "0"
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "--provider", "deepseek", "hi"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=15,
    )
    assert proc.returncode == 1
    combined = (proc.stdout + proc.stderr).lower()
    assert "no credential" in combined
    assert "oh auth login" in combined
