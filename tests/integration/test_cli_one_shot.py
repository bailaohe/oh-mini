"""Integration tests for `oh` one-shot CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run_cli(
    args: list[str],
    env_extra: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "oh_mini", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=30,
    )


def test_cli_one_shot_basic(tmp_path):
    proc = _run_cli(
        ["--provider", "anthropic", "hi there"],
        env_extra={"HOME": str(tmp_path), "ANTHROPIC_API_KEY": "fake"},
        cwd=tmp_path,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "Session:" in proc.stdout


def test_cli_missing_api_key_exits_1(tmp_path):
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "OH_MINI_TEST_FAKE_PROVIDER": "0",
        "OH_MINI_FORCE_FILE_BACKEND": "1",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "--provider", "anthropic", "hi"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=15,
    )
    assert proc.returncode == 1
    out_combined = (proc.stderr + proc.stdout).lower()
    assert "no credential" in out_combined
    assert "oh auth login" in out_combined


def test_cli_version_flag(tmp_path):
    proc = _run_cli(
        ["--version"],
        env_extra={"HOME": str(tmp_path), "ANTHROPIC_API_KEY": "fake"},
    )
    assert proc.returncode == 0
    assert "0.2.0" in proc.stdout
