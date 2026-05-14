"""E2E: oh config set/get/show/unset via subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
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
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "deepseek" in proc.stdout

    proc = _run(["get", "default_provider"], tmp_path)
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
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
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    # File should still exist but key gone.
    p = tmp_path / ".oh-mini" / "settings.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert "default_provider" not in raw

    proc = _run(["show"], tmp_path)
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "<unset>" in proc.stdout or "no credentials stored" in proc.stdout


def test_config_show_with_no_settings_file(tmp_path: Path) -> None:
    proc = _run(["show"], tmp_path)
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "settings file" in proc.stdout
