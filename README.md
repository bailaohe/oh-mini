# oh-mini

> Coding-agent CLI demo built on the [meta-harney](https://github.com/bailaohe/meta-harney) runtime.

A faithful but minimal recreation of OpenHarness's coding-assistant scenarios.
oh-mini ships 10 coding tools (file ops, grep/glob, bash, todo, sub-agent,
notebook edit, web fetch), supports both one-shot and interactive REPL modes,
and persists sessions across runs.

## Install

```bash
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY
```

## Usage

```bash
oh "add a hello() function to src/foo.py and run the tests"
oh                                    # interactive REPL
oh --resume <session-id> "tweak that"
```

## Tools

| Tool | Purpose |
|------|---------|
| `file_read` | Read a file with optional offset/limit |
| `file_write` | Create or overwrite a file |
| `file_edit` | Exact-match string replace in a file |
| `grep` | Pattern search across files |
| `glob` | Match files by pattern |
| `bash` | Run a shell command with timeout |
| `todo_write` | Plan multi-step work |
| `agent` | Spawn a read-only sub-agent |
| `notebook_edit` | Edit cells of a Jupyter notebook |
| `web_fetch` | Fetch URL contents (https only) |

## License

Apache-2.0
