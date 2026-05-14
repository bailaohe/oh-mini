# oh-mini

> A faithful, minimal recreation of OpenHarness's coding-assistant experience,
> built on the [meta-harney](https://github.com/bailaohe/meta-harney) runtime SDK.

oh-mini ships 10 coding tools, supports one-shot and interactive REPL modes,
persists sessions across runs, and can use either Anthropic or OpenAI as the
LLM backend. It's deliberately scoped as a demo of what meta-harney's
domain-agnostic runtime can do on a real coding workload.

## Install

```bash
git clone https://github.com/bailaohe/oh-mini.git
cd oh-mini
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export ANTHROPIC_API_KEY=sk-ant-...     # or OPENAI_API_KEY
```

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

# Use OpenAI instead
oh --provider openai --model gpt-4o "..."

# Skip all permission prompts (dangerous; not recommended outside containers)
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
| `bash` | `{command, timeout?, cwd?}` | Default 60s timeout |
| `todo_write` | `{todos: [{content, status}]}` | Stored in session |
| `agent` | `{description, prompt}` | Read-only sub-agent |
| `notebook_edit` | `{path, cell_index, new_source}` | .ipynb only |
| `web_fetch` | `{url, prompt?}` | https only; 1MB cap |

## Permission model

- Interactive REPL: prompts y/N/a for dangerous tools (`bash`, `file_write`, `file_edit`, `notebook_edit`)
- One-shot mode: allows everything by default (assumes you trust the prompt)
- `--yolo` / `--no-yolo` overrides per invocation

## Session storage

Sessions persist as JSON files under `~/.oh-mini/sessions/`. Override the
location with `--sessions-root <path>`.

## License

Apache-2.0
