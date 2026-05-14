"""E2E: spawn `oh bridge` subprocess, drive full lifecycle.

Uses OH_MINI_TEST_FAKE_PROVIDER=1 + OH_MINI_FORCE_FILE_BACKEND=1 so we skip
real API calls and avoid touching the user's keyring. Parent process's
*_API_KEY env vars are filtered out so the subprocess only sees the fake
key we provide.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest


def _clean_env(tmp_path: Path) -> dict[str, str]:
    """Copy parent env but strip any real provider API keys and pin HOME."""
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    env["HOME"] = str(tmp_path)
    env["OH_MINI_FORCE_FILE_BACKEND"] = "1"
    env["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    # Fake credential so the bridge can be started without prompting.
    env["ANTHROPIC_API_KEY"] = "sk-fake"
    return env


async def _run_bridge_subprocess(tmp_path: Path) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "oh_mini",
        "bridge",
        "--provider",
        "anthropic",
        "--yolo",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_clean_env(tmp_path),
        cwd=tmp_path,
    )


async def _send(proc: asyncio.subprocess.Process, req: dict[str, Any]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(req).encode() + b"\n")
    await proc.stdin.drain()


async def _read_one(proc: asyncio.subprocess.Process) -> dict[str, Any]:
    assert proc.stdout is not None
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
    if not line:
        # subprocess closed stdout; surface stderr for debugging
        assert proc.stderr is not None
        err = await proc.stderr.read()
        raise RuntimeError(f"bridge subprocess exited prematurely. stderr:\n{err.decode()}")
    result: dict[str, Any] = json.loads(line)
    return result


@pytest.mark.asyncio
async def test_bridge_lifecycle_via_subprocess(tmp_path: Path) -> None:
    proc = await _run_bridge_subprocess(tmp_path)
    try:
        # initialize
        await _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        resp = await _read_one(proc)
        assert resp["id"] == 1
        assert resp["result"]["server_info"]["name"] == "oh-mini-bridge"

        # session.create
        await _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "session.create"})
        resp = await _read_one(proc)
        assert resp["id"] == 2
        sid = resp["result"]["id"]

        # tools.list — verify oh-mini's well-known tools are exposed
        await _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools.list"})
        resp = await _read_one(proc)
        assert resp["id"] == 3
        names = sorted(t["name"] for t in resp["result"])
        assert len(names) >= 5
        for expected in ("bash", "file_read", "file_write", "grep", "glob"):
            assert expected in names, f"missing tool: {expected} (got {names})"

        # session.send_message — fake provider returns a canned reply
        await _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "session.send_message",
                "params": {
                    "session_id": sid,
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "hi"}],
                    },
                },
            },
        )
        # Drain until we see id=4 final response; count stream/event notifications.
        got_final = False
        stream_count = 0
        for _ in range(200):
            msg = await _read_one(proc)
            if msg.get("method") == "stream/event":
                stream_count += 1
            elif msg.get("id") == 4:
                got_final = True
                break
        assert got_final
        assert stream_count >= 1

        # shutdown + exit
        await _send(proc, {"jsonrpc": "2.0", "id": 99, "method": "shutdown"})
        await _read_one(proc)
        await _send(proc, {"jsonrpc": "2.0", "method": "exit"})
        assert proc.stdin is not None
        proc.stdin.close()

        await asyncio.wait_for(proc.wait(), timeout=5)
        assert proc.returncode == 0
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
