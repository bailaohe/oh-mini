# Phase 10.5 Implementation Plan — `oh bridge`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Ship `oh bridge` subcommand. After this, `python -m oh_mini bridge` becomes a JSON-RPC server for Phase 11 TUI consumption.

**Architecture:** New `bridge.py` module wires oh-mini's runtime (10 tools + catalog + credentials) into `meta_harney.bridge.BridgeServer`. Permission goes through `BridgePermissionResolver` (or AllowAll with `--yolo`). Telemetry via `BridgeTraceSink`.

**Tech Stack:** Python 3.10+, meta-harney v0.1.0 (new dep), pytest, mypy strict, ruff.

**Spec:** `docs/superpowers/specs/2026-05-14-phase10_5-oh-bridge-design.md`

**Repo:** `/Users/baihe/Projects/study/oh-mini` branch `main`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | meta-harney `@v0.0.8` → `@v0.1.0`; version `0.3.0` → `0.4.0` |
| `src/oh_mini/runtime.py` | Modify | Accept `permission_resolver`/`trace_sink` overrides |
| `src/oh_mini/bridge.py` | Create | `handle_bridge(args)` |
| `src/oh_mini/cli.py` | Modify | Register `bridge` subcommand |
| `src/oh_mini/__init__.py` | Modify | Version 0.4.0 |
| `tests/integration/test_bridge_subprocess.py` | Create | E2E |
| `README.md` | Modify | New section |

---

### Task 1: Bump meta-harney dep to v0.1.0

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump dep**

In `pyproject.toml`, find the meta-harney dep line:

```toml
"meta-harney @ git+https://github.com/bailaohe/meta-harney.git@v0.0.8",
```

Change `@v0.0.8` to `@v0.1.0`.

- [ ] **Step 2: Reinstall**

```bash
.venv/bin/pip install -e ".[dev]" 2>&1 | tail -5
```

Expected: pulls meta-harney v0.1.0; no errors.

- [ ] **Step 3: Verify import surface**

```bash
.venv/bin/python -c "from meta_harney.bridge import BridgeServer, BridgePermissionResolver, BridgeTraceSink, NewlineFraming, ContentLengthFraming; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Run full existing test suite**

```bash
.venv/bin/pytest -q
```

Expected: 140 passed (no regressions from meta-harney upgrade).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "deps: bump meta-harney to v0.1.0 (bridge module available)"
```

---

### Task 2: Refactor `build_runtime` to accept permission_resolver + trace_sink

**Files:**
- Modify: `src/oh_mini/runtime.py`
- Test: `tests/unit/test_runtime_factory.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_runtime_factory.py`:

```python
def test_build_runtime_accepts_permission_resolver_override(tmp_path):
    """When permission_resolver is provided, build_runtime uses it instead of the default."""
    import os

    os.environ["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    try:
        sentinel = _SentinelPermissionResolver()
        rt = build_runtime(
            provider="deepseek",
            api_key="fake",
            sessions_root=tmp_path,
            permission_resolver=sentinel,
        )
        assert rt._permission_resolver is sentinel
    finally:
        os.environ.pop("OH_MINI_TEST_FAKE_PROVIDER", None)


def test_build_runtime_accepts_trace_sink_override(tmp_path):
    import os

    os.environ["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    try:
        sentinel = _SentinelTraceSink()
        rt = build_runtime(
            provider="deepseek",
            api_key="fake",
            sessions_root=tmp_path,
            trace_sink=sentinel,
        )
        assert rt._trace_sink is sentinel
    finally:
        os.environ.pop("OH_MINI_TEST_FAKE_PROVIDER", None)


class _SentinelPermissionResolver:
    """Stand-in for a custom PermissionResolver — duck-typed."""

    async def resolve(self, invocation, session_id):
        from meta_harney.abstractions.permission import PermissionDecision
        return PermissionDecision(verdict="allow")


class _SentinelTraceSink:
    """Stand-in for a custom TraceSink."""

    async def emit(self, event):
        pass

    async def flush(self):
        pass
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/unit/test_runtime_factory.py -v`
Expected: `TypeError: build_runtime() got an unexpected keyword argument 'permission_resolver'`

- [ ] **Step 3: Add override params**

In `src/oh_mini/runtime.py`, replace `build_runtime` signature + body:

```python
from typing import Any

def build_runtime(
    *,
    provider: str = "anthropic",
    api_key: str = "",
    model: str | None = None,
    yolo: bool = False,
    sessions_root: Path | None = None,
    permission_resolver: Any | None = None,
    trace_sink: Any | None = None,
) -> AgentRuntime:
    """...docstring..."""
    if os.environ.get("OH_MINI_TEST_FAKE_PROVIDER") == "1":
        from meta_harney.testing import FakeLLMProvider, FakeRound

        prov = FakeLLMProvider(
            rounds=[FakeRound(text="hello from fake", stop_reason="end_turn") for _ in range(20)]
        )
        chosen_model = model or "fake-model"
    else:
        if provider not in BUILT_IN_PROVIDERS:
            print(f"error: unknown provider {provider!r}. Try: oh providers list", file=sys.stderr)
            sys.exit(2)
        spec = BUILT_IN_PROVIDERS[provider]
        prov = provider_from_spec(spec, api_key=api_key)
        chosen_model = model or spec.default_model

    root = sessions_root or (Path.home() / ".oh-mini" / "sessions")
    root.mkdir(parents=True, exist_ok=True)
    session_store = FileSessionStore(root)

    permission = permission_resolver or InteractiveAskPermissionResolver(yolo=yolo)
    sink = trace_sink or NullSink()
    prompt_builder = CodingPromptBuilder(session_store=session_store)
    tools = build_all_tools()
    config = RuntimeConfig(model=chosen_model, max_iterations=20)
    hooks: list[BaseHook] = []

    multi_agent = InProcessMultiAgentBackend(
        provider=prov,
        permission_resolver=permission,
        session_store=session_store,
        trace_sink=sink,
        config=config,
        all_tools=tools,
        hooks=hooks,
    )

    return AgentRuntime(
        provider=prov,
        prompt_builder=prompt_builder,
        permission_resolver=permission,
        session_store=session_store,
        trace_sink=sink,
        config=config,
        tools=tools,
        hooks=hooks,
        multi_agent=multi_agent,
    )
```

Update the docstring's Args block to add the two new params.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/test_runtime_factory.py -v`
Expected: pass (and all other tests still green).

Full suite: `.venv/bin/pytest -q`
Expected: 142 passed (140 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/runtime.py tests/unit/test_runtime_factory.py
git commit -m "feat(runtime): accept permission_resolver + trace_sink overrides"
```

---

### Task 3: `bridge.py` module — `handle_bridge(args)`

**Files:**
- Create: `src/oh_mini/bridge.py`
- Test: `tests/unit/test_bridge_module.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_bridge_module.py`:

```python
"""Unit tests for oh_mini.bridge module."""

from __future__ import annotations

import argparse

import pytest


def _args(**kwargs) -> argparse.Namespace:
    defaults = {
        "provider_flag": None,
        "profile_flag": None,
        "model": None,
        "api_key": None,
        "framing": "newline",
        "sessions_root": None,
        "yolo": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_select_framing_newline() -> None:
    from oh_mini.bridge import _select_framing
    from meta_harney.bridge import NewlineFraming

    framing = _select_framing("newline")
    assert isinstance(framing, NewlineFraming)


def test_select_framing_content_length() -> None:
    from oh_mini.bridge import _select_framing
    from meta_harney.bridge import ContentLengthFraming

    framing = _select_framing("content-length")
    assert isinstance(framing, ContentLengthFraming)


def test_select_framing_unknown_raises() -> None:
    from oh_mini.bridge import _select_framing

    with pytest.raises(SystemExit):
        _select_framing("totally-fake")


def test_select_permission_resolver_yolo() -> None:
    from oh_mini.bridge import _select_permission_resolver

    resolver = _select_permission_resolver(yolo=True, send_request=None)
    assert resolver.__class__.__name__ == "AllowAllPermissionResolver"


def test_select_permission_resolver_bridge() -> None:
    from oh_mini.bridge import _select_permission_resolver
    from meta_harney.bridge import BridgePermissionResolver

    async def send(method, params):
        return {"decision": "allow"}

    resolver = _select_permission_resolver(yolo=False, send_request=send)
    assert isinstance(resolver, BridgePermissionResolver)
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest tests/unit/test_bridge_module.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement bridge.py**

Create `src/oh_mini/bridge.py`:

```python
"""`oh bridge` — run oh-mini as a JSON-RPC bridge server.

Constructs an AgentRuntime with oh-mini's tools + provider catalog +
credentials, wraps in meta-harney's BridgeServer, serves over stdio.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from meta_harney import BUILT_IN_PROVIDERS
from meta_harney.bridge import (
    BridgePermissionResolver,
    BridgeServer,
    BridgeTraceSink,
    ContentLengthFraming,
    Framing,
    NewlineFraming,
)
from meta_harney.builtin.permission.allow_all import AllowAllPermissionResolver

from oh_mini.auth.resolver import CredentialResolver, NoCredentialError, pick_default_provider
from oh_mini.auth.storage import default_backend
from oh_mini.config import Settings, load_settings
from oh_mini.runtime import build_runtime


def _select_framing(name: str) -> Framing:
    if name == "newline":
        return NewlineFraming()
    if name == "content-length":
        return ContentLengthFraming()
    print(
        f"error: unknown framing {name!r}. Choices: newline, content-length",
        file=sys.stderr,
    )
    sys.exit(2)


def _select_permission_resolver(
    *,
    yolo: bool,
    send_request: Callable[[str, dict[str, Any]], Awaitable[Any]] | None,
) -> Any:
    if yolo:
        return AllowAllPermissionResolver()
    assert send_request is not None, "send_request required when yolo=False"
    return BridgePermissionResolver(send_request=send_request)


def handle_bridge(args: argparse.Namespace) -> int:
    """Entry point for `oh bridge`. Returns process exit code."""
    settings = load_settings()
    backend = default_backend()

    # Resolve provider via the same chain as one-shot / REPL:
    # CLI flag > settings > smart pick > error
    provider_name = (
        getattr(args, "provider_flag", None)
        or settings.default_provider
        or pick_default_provider(backend)
    )
    if provider_name is None:
        print(
            "error: no providers configured. Run: oh auth login --provider <name>",
            file=sys.stderr,
        )
        return 1
    if provider_name not in BUILT_IN_PROVIDERS:
        print(
            f"error: unknown provider {provider_name!r}. Try: oh providers list",
            file=sys.stderr,
        )
        return 2

    profile = getattr(args, "profile_flag", None) or settings.default_profile

    resolver = CredentialResolver(backend)
    try:
        api_key = resolver.resolve(
            provider_name, profile, cli_api_key=getattr(args, "api_key", None)
        )
    except NoCredentialError as exc:
        print(
            f"error: {exc}. Try: oh auth login --provider {provider_name}",
            file=sys.stderr,
        )
        return 1

    framing = _select_framing(getattr(args, "framing", "newline"))
    sessions_root = (
        Path(args.sessions_root) if getattr(args, "sessions_root", None) else None
    )

    asyncio.run(
        _run_server(
            provider=provider_name,
            api_key=api_key,
            model=getattr(args, "model", None),
            yolo=bool(getattr(args, "yolo", False)),
            sessions_root=sessions_root,
            framing=framing,
        )
    )
    return 0


async def _run_server(
    *,
    provider: str,
    api_key: str,
    model: str | None,
    yolo: bool,
    sessions_root: Path | None,
    framing: Framing,
) -> None:
    """Wires the BridgeServer with a runtime whose permission resolver +
    trace sink route back through the bridge."""
    # Create the server first WITHOUT runtime, just so we can pass its
    # send_request bound method to the BridgePermissionResolver, then wire
    # everything. Cheap trick: we instantiate the resolvers with a forward
    # ref to a not-yet-constructed server, then assign.
    #
    # Simpler approach: build the runtime in two steps. We need the runtime
    # before we have the server (BridgeServer takes runtime in __init__),
    # but BridgePermissionResolver needs server.send_request. Solve with a
    # lazy callable.

    server_holder: dict[str, BridgeServer] = {}

    async def lazy_send_request(method: str, params: dict[str, Any]) -> Any:
        server = server_holder.get("server")
        if server is None:
            raise RuntimeError("bridge server not yet initialized")
        return await server.send_request(method, params)

    async def lazy_send_notification(method: str, params: dict[str, Any]) -> None:
        server = server_holder.get("server")
        if server is None:
            return
        # Server has _send_notification but it's underscored; we use it directly.
        await server._send_notification(method, params)  # type: ignore[attr-defined]

    permission = _select_permission_resolver(yolo=yolo, send_request=lazy_send_request)
    trace_sink = BridgeTraceSink(send_notification=lazy_send_notification)

    runtime = build_runtime(
        provider=provider,
        api_key=api_key,
        model=model,
        yolo=False,  # permission_resolver overrides; yolo flag passed via resolver above
        sessions_root=sessions_root,
        permission_resolver=permission,
        trace_sink=trace_sink,
    )

    server = BridgeServer(
        runtime=runtime,
        framing=framing,
        server_info={"name": "oh-mini-bridge", "version": "0.4.0"},
        trace_sink=trace_sink,
    )
    server_holder["server"] = server

    await server.serve_stdio()
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/unit/test_bridge_module.py -v`
Expected: 5 pass.

- [ ] **Step 5: Commit**

```bash
git add src/oh_mini/bridge.py tests/unit/test_bridge_module.py
git commit -m "feat(bridge): handle_bridge wires runtime + BridgeServer over stdio"
```

---

### Task 4: Wire `bridge` subcommand into cli.py

**Files:**
- Modify: `src/oh_mini/cli.py`

- [ ] **Step 1: Register subcommand + dispatch**

In `src/oh_mini/cli.py`:

1. Add `"bridge"` to the `_SUBCOMMANDS` frozenset:

```python
_SUBCOMMANDS = frozenset({"auth", "providers", "config", "bridge"})
```

2. Add `from oh_mini.bridge import handle_bridge` import.

3. In `_build_subcommand_parser()`, after the config subparser block, add:

```python
    # oh bridge ...
    bridge_p = sub.add_parser("bridge", help="run oh-mini as a JSON-RPC bridge server")
    bridge_p.add_argument("--provider", default=None, dest="provider_flag")
    bridge_p.add_argument("--profile", default=None, dest="profile_flag")
    bridge_p.add_argument("--model", default=None)
    bridge_p.add_argument("--api-key", default=None, dest="api_key")
    bridge_p.add_argument(
        "--framing",
        default="newline",
        choices=["newline", "content-length"],
    )
    bridge_p.add_argument("--sessions-root", default=None)
    bridge_p.add_argument("--yolo", action="store_true", default=False)
```

4. In the dispatch chain inside `main()`:

```python
        if args.cmd == "auth":
            rc = handle_auth(args)
        elif args.cmd == "providers":
            rc = _handle_providers(args)
        elif args.cmd == "config":
            rc = handle_config(args)
        elif args.cmd == "bridge":
            rc = handle_bridge(args)
        else:
            parser.print_help()
            rc = 2
```

- [ ] **Step 2: Smoke test**

```bash
.venv/bin/python -m oh_mini bridge --help
```

Expected: help text printed with all flags.

```bash
.venv/bin/python -m oh_mini bridge --provider totally-fake-xyz
```

Expected: exit 2, "unknown provider" error.

- [ ] **Step 3: Run full suite**

```bash
.venv/bin/pytest -q
```

Expected: 147 passed (140 + 2 from T2 + 5 from T3).

- [ ] **Step 4: Commit**

```bash
git add src/oh_mini/cli.py
git commit -m "feat(cli): register oh bridge subcommand"
```

---

### Task 5: E2E subprocess integration test + v0.4.0 release

**Files:**
- Create: `tests/integration/test_bridge_subprocess.py`
- Modify: `pyproject.toml` (version)
- Modify: `src/oh_mini/__init__.py` (version)
- Modify: `README.md` (new Bridge section)
- Modify: `tests/integration/test_cli_one_shot.py` (version assertion 0.3.0 → 0.4.0)

- [ ] **Step 1: Write integration test**

Create `tests/integration/test_bridge_subprocess.py`:

```python
"""E2E: spawn `oh bridge` subprocess, drive full lifecycle."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest


async def _run_bridge_subprocess(tmp_path: Path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["OH_MINI_FORCE_FILE_BACKEND"] = "1"
    env["OH_MINI_TEST_FAKE_PROVIDER"] = "1"
    # Provide a fake credential so the bridge can be started without prompting
    env["ANTHROPIC_API_KEY"] = "sk-fake"
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
        env=env,
        cwd=tmp_path,
    )


async def _send(proc, req: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(req).encode() + b"\n")
    await proc.stdin.drain()


async def _read_one(proc) -> dict:
    assert proc.stdout is not None
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
    return json.loads(line)


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

        # tools.list — verify oh-mini exposes its 10 tools
        await _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools.list"})
        resp = await _read_one(proc)
        assert resp["id"] == 3
        names = sorted(t["name"] for t in resp["result"])
        # at minimum these well-known ones should be present
        for expected in ("bash", "file_read", "file_write", "grep", "glob"):
            assert expected in names, f"missing tool: {expected}"

        # session.send_message — fake provider returns "hello from fake"
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
        # Drain until we see id=4 final response; count stream/event notifications
        got_final = False
        stream_count = 0
        for _ in range(100):
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
        proc.stdin.close()

        await asyncio.wait_for(proc.wait(), timeout=5)
        assert proc.returncode == 0
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
```

- [ ] **Step 2: Run integration test**

```bash
.venv/bin/pytest tests/integration/test_bridge_subprocess.py -v
```

Expected: 1 pass.

- [ ] **Step 3: Bump version + README**

In `pyproject.toml`: `version = "0.4.0"`.

In `src/oh_mini/__init__.py`: `__version__ = "0.4.0"`.

In `tests/integration/test_cli_one_shot.py`: find the version assertion line and change `"0.3.0"` → `"0.4.0"`.

In `README.md`, add after the "Custom providers" section:

```markdown
## Bridge mode

Run oh-mini as a JSON-RPC server for any non-Python client (TUI, IDE plugin):

```bash
oh bridge --provider deepseek
```

The process reads JSON-RPC 2.0 requests from stdin and writes responses /
notifications to stdout. All standard methods from
[`meta_harney.bridge`](https://github.com/bailaohe/meta-harney) are supported:
`initialize`, `shutdown`, `session.{create,list,load,send_message,cancel}`,
`$/cancelRequest`, `tools.list`, `permission/request` (server-initiated),
`telemetry/subscribe`.

**Permission flow:** by default, dangerous tools (`bash`, `file_write`, etc.)
send `permission/request` to the parent process and wait for the decision.
Pass `--yolo` to bypass — runs all tools immediately (CI / standalone testing).

**Framing:** newline-delimited JSON by default. Use `--framing content-length`
for LSP-style framing if payloads get large.
```

- [ ] **Step 4: Final quality gates**

```bash
.venv/bin/pytest -q
.venv/bin/mypy src tests
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/python -m oh_mini --version
```

Expected: all clean, version 0.4.0, 148 tests passed (147 + 1 new integration).

- [ ] **Step 5: Commit + tag v0.4.0**

```bash
git add tests/integration/test_bridge_subprocess.py pyproject.toml src/oh_mini/__init__.py tests/integration/test_cli_one_shot.py README.md
git commit -m "release: v0.4.0 — oh bridge subcommand

Phase 10.5 ships:
- oh bridge: run oh-mini as a JSON-RPC bridge server over stdio
- BridgePermissionResolver wires permission/request to parent (--yolo bypass)
- BridgeTraceSink forwards trace events on telemetry/subscribe
- runtime.build_runtime accepts permission_resolver + trace_sink overrides
- meta-harney dep bumped to v0.1.0"

git tag -a v0.4.0 -m "v0.4.0 — Phase 10.5 oh bridge"
```

---

## Self-Review

**Spec coverage:**
- ✅ Subcommand registration (T4)
- ✅ Smart credential resolution chain re-used (T3 handle_bridge)
- ✅ Permission strategy: BridgePermissionResolver default + --yolo (T3)
- ✅ Telemetry: BridgeTraceSink wired (T3)
- ✅ Framing choice via --framing (T3 + T4)
- ✅ E2E subprocess test (T5)
- ✅ Version bump + README + tag (T5)

**Placeholder scan:** No TBDs. Every step has full code or precise instructions.

**Type consistency:**
- `handle_bridge(args) -> int` matches dispatch pattern (T3, T4)
- `_select_framing(str) -> Framing` returns the Protocol type (T3)
- `permission_resolver: Any | None` in build_runtime — keeps runtime.py free of bridge imports (T2)
- `lazy_send_request` matches `BridgePermissionResolver.send_request` signature (T3)

**Risk callouts:**
- T3 uses a "server_holder dict" trick to delay BridgeServer reference until after construction. This is mildly inelegant but avoids restructuring meta-harney's BridgeServer API. Alternative: meta-harney could expose `send_request` as a free function bound after construction. Not blocking.
- T5 test relies on `OH_MINI_TEST_FAKE_PROVIDER=1` to skip real LLM calls. The fake provider doesn't trigger tools, so we don't exercise permission/request in this test. A follow-up could mock parent-side and verify permission round-trip.

All clear.

---

## Execution

**Subagent-Driven** per the standing preference. Continue uninterrupted.
