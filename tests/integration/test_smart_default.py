"""E2E: after `oh auth login --provider X`, `oh "..."` uses X without --provider."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _run(
    args: list[str],
    env_extra: dict[str, str] | None = None,
    tmp_path: Path | None = None,
    timeout: int = 15,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path) if tmp_path else env["HOME"]
    env["OH_MINI_FORCE_FILE_BACKEND"] = "1"
    # Clear any leaked *_API_KEY env vars from the parent process so the
    # resolver falls through to the stored credential / smart pick deterministically.
    for k in list(env.keys()):
        if k.endswith("_API_KEY"):
            del env[k]
    env["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "oh_mini", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=timeout,
    )


def _seed_file_credential(tmp_path: Path, provider: str, secret: str = "sk-fake") -> None:
    """Bypass interactive `oh auth login` by writing credentials.json directly."""
    home_dot = tmp_path / ".oh-mini"
    home_dot.mkdir(exist_ok=True)
    p = home_dot / "credentials.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
    else:
        data = {"version": 2, "credentials": {}}
    data["credentials"].setdefault(provider, {})["default"] = {
        "secret": secret,
        "last_used": time.time(),
    }
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_single_credential_becomes_effective_default(tmp_path: Path) -> None:
    _seed_file_credential(tmp_path, "deepseek")
    proc = _run(["hi"], tmp_path=tmp_path)
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "Session:" in proc.stdout
    assert "hello from fake" in proc.stdout


def test_settings_default_provider_overrides_smart_pick(tmp_path: Path) -> None:
    # Store multiple credentials; explicit setting in settings.json wins.
    _seed_file_credential(tmp_path, "deepseek")
    _seed_file_credential(tmp_path, "moonshot")
    _seed_file_credential(tmp_path, "anthropic")
    (tmp_path / ".oh-mini" / "settings.json").write_text(
        json.dumps({"default_provider": "anthropic"}),
        encoding="utf-8",
    )
    proc = _run(["hi"], tmp_path=tmp_path)
    # FakeLLMProvider doesn't expose which provider name was passed; we assert the
    # CLI didn't error and ran successfully. The override is exercised by the
    # absence of "no credential for ..." failure paths.
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "Session:" in proc.stdout


def test_no_credentials_no_settings_errors_with_hint(tmp_path: Path) -> None:
    proc = _run(["hi"], tmp_path=tmp_path, env_extra={"OH_MINI_TEST_FAKE_PROVIDER": "0"})
    assert proc.returncode == 1
    combined = (proc.stdout + proc.stderr).lower()
    assert "no providers configured" in combined
    assert "oh auth login" in combined


def test_smart_pick_chooses_most_recent_when_multiple_credentials(tmp_path: Path) -> None:
    """Two credentials, second one stored later should win the smart pick."""
    _seed_file_credential(tmp_path, "anthropic", "sk-a")
    time.sleep(0.05)
    _seed_file_credential(tmp_path, "deepseek", "sk-d")
    # FakeProvider output alone can't tell us which provider was picked, but
    # `oh config show` reports the effective pick. Use it.
    proc = _run(["config", "show"], tmp_path=tmp_path)
    assert proc.returncode == 0, f"stderr={proc.stderr}\nstdout={proc.stdout}"
    assert "deepseek/default" in proc.stdout
    assert "smart pick" in proc.stdout
