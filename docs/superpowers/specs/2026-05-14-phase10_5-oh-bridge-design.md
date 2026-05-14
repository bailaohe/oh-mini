# Phase 10.5 — `oh bridge` subcommand

## Goal

Expose oh-mini as a bridge server. After this phase, any Phase 11 TUI / IDE
plugin runs `python -m oh_mini bridge` to get a fully-wired backend with all
10 coding tools, real provider catalog, credential storage, and
permission/telemetry round-trips.

## Architecture

```
TUI / IDE / test                         oh-mini bridge process
    │                                            │
    └── spawn `oh bridge` ────────────────►  argparse → handle_bridge(args)
        stdin ◄── JSON-RPC ───►  stdout         │
                                                ▼
                                       build_runtime(
                                         permission_resolver=
                                           BridgePermissionResolver(...)
                                         ,
                                         trace_sink=BridgeTraceSink(...)
                                       )
                                                │
                                                ▼
                                       BridgeServer(runtime,
                                                    framing=...,
                                                    trace_sink=...)
                                                │
                                                ▼
                                       server.serve_stdio()
```

## Bump dependencies

`pyproject.toml`: meta-harney git URL `@v0.0.8` → `@v0.1.0` (the bridge module
lives in 0.1.0). oh-mini bumps `0.3.0` → `0.4.0`.

## CLI surface

```
oh bridge [options]

Options:
  --provider X            Provider name (smart-default if omitted)
  --profile P             Profile (default: default)
  --model M               Override model
  --api-key K             Override credential
  --framing F             newline | content-length (default: newline)
  --sessions-root DIR     Override session store path
  --yolo                  Bypass BridgePermissionResolver, use AllowAll
                          (for CI / standalone testing)
```

After flag parsing, the process becomes a bridge server. stderr is for
human-readable logs (parent process should drain or ignore).

## Permission strategy

Default: `BridgePermissionResolver`. Every dangerous tool invocation
(`bash`, `file_write`, `file_edit`, `notebook_edit`, `web_fetch`) sends
`permission/request` UP to the parent and awaits the decision. With
`--yolo`, falls back to `AllowAllPermissionResolver`.

## Telemetry

A `BridgeTraceSink` replaces the default `NullTraceSink`. By default the
sink is disabled — events are dropped at the sink. The parent process can
call `telemetry/subscribe {enabled: true}` to opt in.

## Files

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Bump meta-harney dep + oh-mini version |
| `src/oh_mini/runtime.py` | Modify | Accept optional `permission_resolver` + `trace_sink` overrides |
| `src/oh_mini/bridge.py` | Create | `handle_bridge(args)` builds runtime + server, runs serve_stdio |
| `src/oh_mini/cli.py` | Modify | Register `bridge` subcommand |
| `src/oh_mini/__init__.py` | Modify | Version 0.4.0 |
| `tests/integration/test_bridge_subprocess.py` | Create | Spawn `python -m oh_mini bridge`, drive lifecycle + send_message |
| `README.md` | Modify | New "Bridge mode" section |

## Method surface (delegated to meta-harney)

`oh bridge` does NOT add new RPC methods. Everything available in
`meta_harney.bridge.BridgeServer` is automatically exposed:

- Lifecycle: initialize / shutdown / exit
- Sessions: session.{create,list,load}
- Streaming: session.send_message → stream/event notifications
- Cancellation: $/cancelRequest, session.cancel
- Tools: tools.list (returns oh-mini's 10 coding tools)
- Permissions: permission/request (S→C) for dangerous tools
- Telemetry: telemetry/subscribe + telemetry/event

## Smoke test (manual)

```bash
# Terminal 1
oh bridge --provider deepseek

# Terminal 2 (or pipe in JSON)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | oh bridge ...
```

(Real usage uses subprocess pipes from a parent process — see integration test.)

## Acceptance

1. `oh bridge --help` prints subcommand usage
2. `python -m oh_mini bridge` (with deepseek key configured) starts a bridge,
   integration test drives initialize → session.create → send_message →
   stream/event → final response → shutdown → exit, process exits 0
3. With `--yolo`, dangerous tools execute without permission/request round-trip
4. Without `--yolo`, dangerous tool execution triggers `permission/request`
   notification (integration test mocks the parent's response)
5. `pytest -q` 100% green (existing 140 + new bridge integration tests)
6. mypy strict + ruff clean
7. Released as v0.4.0

## Out of scope

- New RPC methods (Phase 11 will identify gaps)
- Authentication / process trust
- Multi-client per server
- Phase 11 TUI itself

## Versioning

oh-mini `0.3.0` → **`0.4.0`** (new subcommand + dep bump).
