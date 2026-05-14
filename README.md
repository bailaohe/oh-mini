# oh-mini

> A coding-agent CLI built on the [meta-harney](https://github.com/bailaohe/meta-harney) runtime SDK.

Supports 9 LLM providers out of the box (Anthropic, OpenAI, DeepSeek, Moonshot,
Gemini, MiniMax, NVIDIA, Dashscope, ModelScope), persists sessions across runs,
and stores credentials via system keyring (with file fallback). User-defined
providers via `~/.oh-mini/settings.json`.

## Install

```bash
git clone https://github.com/bailaohe/oh-mini.git
cd oh-mini
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Store a credential (uses system keyring if available, else file 0600)
oh auth login --provider anthropic
# (interactive; enter API key, hidden input)

# Then run
oh "list the python files in the current directory"
```

After `oh auth login --provider <X>` your first credential becomes the
*effective default* automatically — subsequent `oh "..."` commands use it
without a `--provider` flag. To override, see [Defaults](#defaults) below.

Or skip storage and use env var:

```bash
ANTHROPIC_API_KEY=sk-ant-... oh "..."
```

## Supported providers

```bash
oh providers list
```

```
name           kind       default_model                base_url                                                description
anthropic      anthropic  claude-sonnet-4-5            (SDK default)                                           Anthropic Claude (official)
openai         openai     gpt-4o                       (SDK default)                                           OpenAI (official)
moonshot       openai     kimi-k2-0905-preview         https://api.moonshot.cn/v1                              Moonshot AI (Kimi, OpenAI-compatible)
deepseek       openai     deepseek-chat                https://api.deepseek.com/v1                             DeepSeek (OpenAI-compatible)
gemini         openai     gemini-2.0-flash             https://generativelanguage.googleapis.com/v1beta/openai Google Gemini (OpenAI-compatible)
minimax        openai     MiniMax-M2                   https://api.minimax.io/v1                               MiniMax (OpenAI-compatible)
nvidia         openai     meta/llama-3.1-405b-instruct https://integrate.api.nvidia.com/v1                     NVIDIA NIM (OpenAI-compatible)
dashscope      openai     qwen-max                     https://dashscope.aliyuncs.com/compatible-mode/v1       Alibaba Dashscope (OpenAI-compatible)
modelscope     openai     Qwen/Qwen2.5-72B-Instruct    https://api-inference.modelscope.cn/v1                  ModelScope (OpenAI-compatible)
```

Switch with `--provider`:

```bash
oh --provider deepseek "task description"
oh --provider moonshot --model kimi-k2-0905-preview "..."
```

## Credential management

```bash
oh auth login --provider deepseek
oh auth login --provider deepseek --profile work    # separate key per profile
oh auth list                                        # show all stored
oh auth show --provider deepseek                    # show profiles for one
oh auth remove --provider deepseek --profile work   # delete
```

**Resolution priority (highest first):**
1. `--api-key sk-...` flag
2. env var `<PROVIDER>_API_KEY` (e.g. `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`)
3. stored credential (keyring or file)

**Storage backend:** keyring (macOS Keychain / Linux Secret Service /
Windows Credential Manager) if available; otherwise plain JSON at
`~/.oh-mini/credentials.json` with POSIX mode 0600.

## Defaults

Provider resolution order (highest first):

1. `--provider <X>` CLI flag
2. `default_provider` in `~/.oh-mini/settings.json` (if set)
3. Smart pick: the stored credential with the most recent `last_used`
   timestamp (the credential you most recently logged in or used)
4. Error: prompts you to `oh auth login --provider <X>`

### `oh config` CLI

```bash
oh config show                                # show settings + effective default
oh config get default_provider                # read one setting
oh config set default_provider deepseek       # pin a default
oh config unset default_provider              # revert to smart pick
```

Known settings keys: `default_provider`, `default_profile`.

## Custom providers

Add your own OpenAI-compatible endpoint via `~/.oh-mini/settings.json`:

```json
{
  "default_provider": "deepseek",
  "default_profile": "default",
  "custom_providers": [
    {
      "name": "my-local-llama",
      "kind": "openai",
      "base_url": "http://localhost:8080/v1",
      "default_model": "llama-3.1-8b"
    }
  ]
}
```

Then `oh --provider my-local-llama "..."` works the same as a built-in.
Custom providers can override built-ins by reusing the name.

## Usage

```bash
# One-shot
oh "in src/foo.py, add a bar() function and run the tests"

# Interactive REPL
oh
oh> /sessions
oh> /clear
oh> /exit

# Continue a previous session
oh --resume <session-id> "tweak it"

# Skip all permission prompts (dangerous outside containers)
oh --yolo "..."
```

## Tools

| Tool | Schema | Notes |
|------|--------|-------|
| `file_read` | `{path, offset?, limit?}` | UTF-8 text |
| `file_write` | `{path, content}` | Overwrites |
| `file_edit` | `{path, old_string, new_string, replace_all?}` | Exact match |
| `grep` | `{pattern, path?, glob?, max_matches?}` | Recursive regex |
| `glob` | `{pattern, path?}` | Supports `**` |
| `bash` | `{command, timeout?, cwd?}` | 60s timeout default |
| `todo_write` | `{todos: [{content, status}]}` | Stored in session |
| `agent` | `{description, prompt}` | Read-only sub-agent |
| `notebook_edit` | `{path, cell_index, new_source}` | .ipynb only |
| `web_fetch` | `{url, prompt?}` | https only; 1MB cap |

## Permission model

- Interactive REPL: prompts y/N/a for dangerous tools (`bash`, `file_write`,
  `file_edit`, `notebook_edit`)
- One-shot mode: allows everything by default (assumes you trust the prompt)
- `--yolo` / `--no-yolo` overrides per invocation

## Session storage

Sessions persist as JSON files under `~/.oh-mini/sessions/`. Override with
`--sessions-root <path>`.

## License

Apache-2.0
