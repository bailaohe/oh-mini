"""Integration test: --resume picks up an existing session."""
from __future__ import annotations

import os
import re
import subprocess
import sys


def test_resume_continues_existing_session(tmp_path):
    env = os.environ.copy()
    env.update({
        "HOME": str(tmp_path),
        "ANTHROPIC_API_KEY": "fake",
        "OH_MINI_TEST_FAKE_PROVIDER": "1",
    })

    # First run: capture session id
    proc1 = subprocess.run(
        [sys.executable, "-m", "oh_mini", "first message"],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=15,
    )
    assert proc1.returncode == 0, f"stderr={proc1.stderr}\nstdout={proc1.stdout}"
    m = re.search(r"Session:\s+(\S+)", proc1.stdout)
    assert m, f"no Session: id in output\n{proc1.stdout}"
    sid = m.group(1)

    # Second run: --resume
    proc2 = subprocess.run(
        [sys.executable, "-m", "oh_mini", "--resume", sid, "follow-up"],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=15,
    )
    assert proc2.returncode == 0, f"stderr={proc2.stderr}\nstdout={proc2.stdout}"
    assert sid in proc2.stdout


def test_resume_unknown_session_exits_2(tmp_path):
    env = os.environ.copy()
    env.update({
        "HOME": str(tmp_path),
        "ANTHROPIC_API_KEY": "fake",
        "OH_MINI_TEST_FAKE_PROVIDER": "1",
    })
    proc = subprocess.run(
        [sys.executable, "-m", "oh_mini", "--resume", "nonexistent-id", "x"],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=15,
    )
    assert proc.returncode == 2
    combined = (proc.stdout + proc.stderr).lower()
    assert "no such session" in combined
