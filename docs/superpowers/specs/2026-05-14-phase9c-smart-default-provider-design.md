# Phase 9c — Smart default provider + `oh config` CLI

## Goal

After `oh auth login --provider deepseek`, running plain `oh "task"` should *just work* without manually editing `~/.oh-mini/settings.json`. Today it fails with `no credential for anthropic/default` because the default is hard-coded.

## Background

Phase 9b shipped:
- `~/.oh-mini/settings.json` with `default_provider: str = "anthropic"` (hard default)
- `keyring` / `FileBackend` credential storage
- `oh auth login/list/remove/show` subcommands
- `CredentialResolver` priority: CLI flag > env var > backend → error

Gap: there's no link between "I stored a credential" and "that credential gets used by default". The default is frozen at `"anthropic"` until the user edits the JSON.

## Design

### 1. Smart fallback chain

Provider name resolution becomes:

```
1. --provider <X>             # CLI flag (highest)
2. settings.default_provider  # IF explicitly set in settings.json (not None)
3. pick_default_provider()    # backend-driven smart pick
4. error: "no providers configured. Try: oh auth login --provider <X>"
```

`pick_default_provider(backend)`:
- backend has 0 credentials → return `None` (caller emits error #4)
- backend has 1 credential → return that one's provider name
- backend has N credentials → return the one with **largest `last_used` timestamp**

### 2. Settings becomes opt-in for `default_provider`

```python
@dataclass
class Settings:
    default_provider: str | None = None  # was: "anthropic"
    default_profile: str = "default"
```

`None` semantics: "fall back to smart pick". A user that explicitly writes `"default_provider": "deepseek"` in settings.json gets it honored verbatim (priority #2 above).

Backward compatibility: an old settings.json with `"default_provider": "anthropic"` keeps working (explicit value). Only the *hard default* changes.

### 3. Credentials gain `last_used` metadata

Both backends record when a credential was last successfully used (read or written).

**FileBackend** — `~/.oh-mini/credentials.json` shape change:

```jsonc
// OLD (v0.2.0):
{ "deepseek:default": "sk-deepseek-..." }

// NEW (v0.3.0):
{
  "deepseek:default": {
    "secret": "sk-deepseek-...",
    "last_used": 1715731200.0
  }
}
```

**KeyringBackend** — secret stays in the OS keyring; sidecar index file at `~/.oh-mini/keyring-index.json` upgrades from:

```jsonc
// OLD: ["deepseek:default", "anthropic:default"]
// NEW:
{
  "deepseek:default": { "last_used": 1715731200.0 },
  "anthropic:default": { "last_used": 1715731100.0 }
}
```

**Migration is read-time, lazy, transparent:**
- `_load()` detects old format and synthesizes `last_used=0.0` per entry
- The next successful `put()` or `touch()` writes the new format
- No migration script needed

### 4. `CredentialBackend` API additions

```python
class CredentialBackend(Protocol):
    def get(self, key: CredentialKey) -> str | None: ...
    def put(self, key: CredentialKey, secret: str) -> None: ...   # writes last_used=now
    def delete(self, key: CredentialKey) -> None: ...
    def list(self) -> list[CredentialKey]: ...
    def touch(self, key: CredentialKey) -> None: ...              # NEW: updates last_used only
    def get_last_used(self, key: CredentialKey) -> float: ...     # NEW: returns 0.0 if missing
```

`CredentialResolver.resolve()` calls `backend.touch(key)` after a successful backend hit (steps 1–2, CLI flag / env var, do NOT touch — they don't go through the backend).

### 5. `oh config` subcommand (minimal set)

```bash
oh config show                                # prints effective config
oh config get default_provider                # prints raw stored value
oh config set default_provider deepseek       # writes settings.json atomically
oh config unset default_provider              # removes key, falls back to smart pick
```

Allowed keys: `default_provider`, `default_profile`. Other keys → error.

`oh config set default_provider <X>` validates `<X> ∈ BUILT_IN_PROVIDERS ∪ custom_providers`.

`oh config show` output:

```
settings file: /Users/baihe/.oh-mini/settings.json
default_provider: deepseek         (from settings.json)
default_profile:  default          (default)

effective provider for next `oh ...`:
  deepseek/default  (from settings.json)
```

When no settings + 2 stored creds:

```
settings file: /Users/baihe/.oh-mini/settings.json (not present)
default_provider: <unset>
default_profile:  default          (default)

effective provider for next `oh ...`:
  moonshot/default  (smart pick: most recently used of [anthropic, moonshot])
```

### 6. Friendly nudge on first login

When `oh auth login --provider X` completes AND the backend now contains exactly 1 credential AND `settings.default_provider` is None, print:

```
Stored deepseek/default.
(deepseek is now your effective default — run `oh "..."` to use it.)
```

Otherwise, just `Stored deepseek/default.`

### 7. File structure

```
src/oh_mini/
├── config.py              # MODIFY: Settings.default_provider -> Optional[str]
│                          # ADD: save_settings(), update_setting(), unset_setting()
├── config_cli.py          # NEW: handle_config(args) dispatcher
├── auth/
│   ├── storage.py         # MODIFY: metadata format, touch(), get_last_used()
│   ├── resolver.py        # MODIFY: touch() after hit; add pick_default_provider()
│   └── cli.py             # MODIFY: friendly nudge after login
└── cli.py                 # MODIFY: register `config` subcommand + new resolution chain
```

## Error handling

| Scenario | Behavior |
|---|---|
| `oh config set default_provider unknown-name` | exit 2, `error: unknown provider 'unknown-name'. Try: oh providers list` |
| `oh config set unknown_key x` | exit 2, `error: unknown setting 'unknown_key'. Known: default_provider, default_profile` |
| `oh config unset` on a key that isn't set | exit 0, no-op, print `(default_provider was not set)` |
| `oh "task"` with no creds + no env | exit 1, `error: no providers configured. Run: oh auth login --provider <X>` |
| settings.json corrupt | Same as 9b: warn to stderr, treat as defaults |
| credentials.json corrupt | Same as 9b: raise `CredentialStorageError` |
| old-format credentials.json | Read transparently; rewrite to new format on next put/touch |

## Testing strategy

| Test file | Coverage |
|---|---|
| `tests/unit/test_config.py` (extend) | `default_provider=None` default · `save_settings()` atomicity · `update_setting()` round-trip · `unset_setting()` |
| `tests/unit/test_config_cli.py` (new) | `set/get/show/unset` happy paths · unknown key/provider · show formatting |
| `tests/unit/auth/test_file_backend.py` (extend) | New metadata format · `touch()` updates `last_used` · old format read compat · old → new rewrite on put |
| `tests/unit/auth/test_keyring_backend.py` (extend) | Index file metadata format · old list format compat · `touch()` updates index |
| `tests/unit/auth/test_resolver.py` (extend) | `touch()` called on backend hit · NOT called on CLI/env hit · `pick_default_provider()` 0/1/N scenarios |
| `tests/integration/test_smart_default.py` (new) | E2E: `auth login deepseek` then `oh "..."` uses deepseek without `--provider` · 2 logins, second wins via timestamp · `oh config set default_provider X` overrides smart pick |
| `tests/integration/test_config_cli.py` (new) | E2E: `oh config set/show/unset` via subprocess |

## Out of scope (deferred)

- `oh config provider add/remove` (CRUD on custom_providers) — Phase 9d candidate
- Encrypted credentials — Phase 10+
- Migration script for v0.2.x users — automatic lazy migration covers it
- Per-provider default model override in settings — already works via `--model`

## Acceptance

1. `oh auth login --provider deepseek` (no settings.json) → `oh "hi"` resolves to deepseek without `--provider` flag
2. Two logins (anthropic then moonshot) → `oh "hi"` uses moonshot
3. `oh config set default_provider anthropic` overrides the timestamp pick
4. `oh config unset default_provider` returns to timestamp-based smart pick
5. v0.2.x credentials.json still loads (old shape preserved on read; rewritten on next write)
6. All existing 97 tests still pass
7. mypy strict + ruff check + ruff format clean
