"""Integration test for `oh` REPL mode (driven via subprocess.PIPE)."""

from __future__ import annotations

import os
import subprocess
import sys


def test_repl_single_turn_then_exit(tmp_path):
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "ANTHROPIC_API_KEY": "fake",
            "OH_MINI_TEST_FAKE_PROVIDER": "1",
            "OH_MINI_TEST_REPL_FORCE": "1",
        }
    )
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini"],
        input="hi\n/exit\n",
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=15,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "hello from fake" in proc.stdout or "Session:" in proc.stdout


def test_repl_clear_command(tmp_path):
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "ANTHROPIC_API_KEY": "fake",
            "OH_MINI_TEST_FAKE_PROVIDER": "1",
            "OH_MINI_TEST_REPL_FORCE": "1",
        }
    )
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini"],
        input="/clear\n/exit\n",
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=15,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert proc.stdout.count("Session:") >= 2
