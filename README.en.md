# ai-cli-statusline

A local-first usage status bar for AI CLI tools. It provides a unified view of tokens, context usage, and rate limits for Codex, Claude Code, and Kimi Code.

[中文 README](README.md)

## Features

- Unified ANSI status-line and JSON output.
- One-shot `status` and continuously refreshing `watch` commands.
- Codex: reads account limits through `codex app-server --stdio` and reads local session tokens and model metadata in read-only mode.
- Claude Code: scans local session logs and supports Claude's official `statusLine` stdin protocol.
- Kimi Code: scans configurable local session directories and supports Kimi's official `[status_line].command` stdin protocol.
- Progress bars use `█` and `░`; percentages are explicitly labeled as usage.

## Installation

Python 3.10 or newer is required. The project uses only the Python standard library.

```bash
cd ai-cli-statusline
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Run directly from source if you do not want to install the package:

```bash
PYTHONPATH=src /usr/local/bin/python3.11 -m ai_cli_statusline status --no-color
```

## Usage

Show a single snapshot:

```bash
ai-cli-statusline status --providers codex,claude,kimi
```

Refresh continuously:

```bash
ai-cli-statusline watch --providers codex,claude,kimi --interval 10
```

Emit machine-readable JSON:

```bash
ai-cli-statusline status --json --no-color
```

`--providers` accepts a comma-separated list of `codex`, `claude`, and `kimi`. An unavailable provider is reported as unavailable; the tool never fabricates usage data.

## Native CLI integrations

Print the integration instructions for a provider:

```bash
ai-cli-statusline integrate claude
ai-cli-statusline integrate kimi
ai-cli-statusline integrate codex
```

### Claude Code

Claude Code runs a configured `statusLine` command, passes session JSON to its stdin, and renders the command's stdout in the footer. Merge the output of `integrate claude` into `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "ai-cli-statusline claude-statusline",
    "refreshInterval": 5
  }
}
```

Test the adapter with mock input:

```bash
printf '%s\n' '{"model":{"display_name":"Sonnet"},"context_window":{"used_percentage":25,"context_window_size":200000}}' \
  | ai-cli-statusline claude-statusline
```

### Kimi Code

Recent Kimi Code releases use `~/.kimi-code/tui.toml`; older releases may use `~/.kimi/tui.toml`. Add:

```toml
[status_line]
command = "ai-cli-statusline kimi-statusline"
```

Run `/reload-tui` in Kimi after editing the file. Kimi limits custom status-line command execution time, so keep the command lightweight.

### Codex

The native Codex footer currently uses built-in `tui.status_line` items and does not expose an external command callback. This project therefore uses two layers:

1. Keep Codex's native token, context, and limit fields enabled.
2. Use a Stop Hook for a colored usage summary; run `watch` when continuous external refresh is needed.

The project does not present external output as Codex's native TUI footer.

## Data and privacy

- Reads only local CLI state databases, session logs, or read-only app-server interfaces.
- Does not read, print, or commit API keys, OAuth credentials, or authentication files.
- Does not output full prompts, responses, or transcript bodies.
- Codex SQLite access uses a read-only connection and `PRAGMA query_only=ON`.
- Missing CLIs and unrecognized logs are reported as unavailable.

## Verification

```bash
PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q
```

Offline tests cover progress-bar boundaries, unified rendering, nested usage aggregation, configurable log roots, and stdin status-line protocols. Claude Code is installed on the current machine; Kimi Code is not installed, so Kimi TUI integration has not been verified against a live session.

## Project status

See [ROADMAP.md](ROADMAP.md) for current progress and open verification items. Open-source publication, remote pushes, and production deployment are not performed by default.

## License

[MIT License](LICENSE)
