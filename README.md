# tokenbar

本地优先的多 AI CLI 用量状态栏工具，为 Codex、Claude Code、Kimi Code 和 OpenCode 提供统一的 token、上下文和额度展示。

[English README](README.en.md)

主命令是 `tokenbar`；旧命令 `ai-cli-statusline` 仍作为兼容别名保留。

![终端状态栏效果演示](docs/demo-statusline.svg)

> 图片为演示输出，数值为模拟数据，不代表真实账户额度。

## 特性

- 统一 ANSI 状态栏和 JSON 输出。
- 支持一次性查询 `status` 和持续刷新 `watch`。
- Codex：通过 `codex app-server --stdio` 读取账户额度，并以只读方式读取本地会话 token 和模型。
- Claude Code：扫描本地会话日志，也支持 Claude 官方 `statusLine` stdin 协议。
- Kimi Code：扫描 `wire.jsonl` 和可配置的本地会话目录，也支持 Kimi 官方 `[status_line].command` stdin 协议。
- OpenCode：通过正向白名单只读本地 `session.tokens_*` 汇总列，不读取消息正文。
- 其他工具按 stable、experimental、planned 分级；`auto` 只启用有专用 reader 和回归证据的 stable provider。
- 进度条使用 `█` 和 `░`，额度百分比明确标注为已用比例。

## 安装

需要 Python 3.10 或更高版本；Python 3.10 会安装 `tomli` 作为标准库 `tomllib` 的兼容依赖。

```bash
cd tokenbar
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

### 三步开始

```bash
tokenbar status
tokenbar watch --interval 5
tokenbar status --json --no-color
```

如果你只想启用某一个工具，可以缩小范围：

```bash
tokenbar status --providers claude
tokenbar status --providers kimi
```

也可以直接从源码运行：

```bash
PYTHONPATH=src /usr/local/bin/python3.11 -m ai_cli_statusline status --no-color
```

## 使用

查看一次状态：

```bash
tokenbar status --providers codex,claude,kimi
```

持续刷新：

```bash
tokenbar watch --providers codex,claude,kimi --interval 10
```

选择主题调色板：

```bash
tokenbar status --theme catppuccin-mocha
tokenbar watch --theme nord
tokenbar status --theme dracula
```

可选主题：`catppuccin-mocha`、`nord`、`dracula`、`default`。也可以通过 `AI_CLI_STATUSLINE_THEME` 设置默认主题；Claude／Kimi 原生状态栏命令会读取同一个环境变量。

进度条也可以切换为纯文本／像素风格，不使用 emoji：

```bash
tokenbar watch --progress-style ascii
tokenbar watch --progress-style thin
tokenbar watch --progress-style dots
```

可选样式：`blocks`、`ascii`、`thin`、`dots`。也可以设置 `AI_CLI_STATUSLINE_PROGRESS_STYLE`；Claude／Kimi 原生状态栏会读取同一个环境变量。

输出机器可读 JSON：

```bash
tokenbar status --json --no-color
```

`--providers` 接受逗号分隔的 provider。单个 provider 不可用时会显示 unavailable，不会伪造数据。

## 接入原生 CLI

先查看对应配置说明：

```bash
tokenbar integrate claude
tokenbar integrate kimi
tokenbar integrate codex

# 自动写入配置；已有配置默认不覆盖
tokenbar setup claude
tokenbar setup kimi
```

### Claude Code

Claude Code 的 `statusLine` 命令会从 stdin 接收会话 JSON，并把脚本 stdout 显示在底部状态栏。将 `integrate claude` 输出的配置合并到 `~/.claude/settings.json`：

```json
{
  "statusLine": {
    "type": "command",
    "command": "tokenbar claude-statusline",
    "refreshInterval": 5
  }
}
```

测试适配器：

```bash
printf '%s\n' '{"model":{"display_name":"Sonnet"},"context_window":{"used_percentage":25,"context_window_size":200000}}' \
  | tokenbar claude-statusline
```

### Kimi Code

新版 Kimi Code 使用 `~/.kimi-code/tui.toml`；旧版可能使用 `~/.kimi/tui.toml`。加入：

```toml
[status_line]
command = "tokenbar kimi-statusline"
```

修改后在 Kimi 中执行 `/reload-tui`。Kimi 的自定义状态栏命令有执行时间限制，命令应保持轻量。

`setup` 会在修改前创建 `.bak` 备份；已有 `[status_line]` 时默认停止，确认覆盖才使用 `--force`。

### Codex

Codex 原生底部栏目前使用内置 `tui.status_line` 项目，不提供外部命令回调。因此本工具采用两层方式：

1. 保留 Codex 原生的 token、上下文和额度字段。
2. 使用 Stop Hook 输出彩色用量摘要；需要持续刷新时运行本工具的 `watch`。

本项目不会把外部输出冒充成 Codex 原生 TUI 底部栏。

### 其他 CLI 和自定义日志

使用 `auto` 可以一次检查所有 stable provider：

```bash
tokenbar status --providers auto
```

内置 provider 和数据来源：

| 成熟度 | provider | 本地来源与读取方式 |
| --- | --- | --- |
| stable（进入 `auto`） | `codex` | app-server 只读额度 RPC + `state_*.sqlite` 明确字段 |
| stable（进入 `auto`） | `claude` | `~/.claude/projects/**/*.jsonl` + statusLine 缓存 |
| stable（进入 `auto`） | `kimi` | `~/.kimi-code/**/wire.jsonl` + status_line 缓存 |
| stable（进入 `auto`） | `opencode` | `opencode.db`／`db.sqlite` 的 `session.tokens_*` 白名单列 |
| experimental（仅显式启用） | `cursor` | 隐私受限；不读取本地 auth token，因此当前不返回用量 |
| experimental（仅显式启用） | `gemini`、`antigravity`、`deepseek`、`pi`、`omp`、`omo`、`craft`、`reasonix` | 常见日志目录上的通用 JSONL reader，尚无逐 provider schema 证据 |
| planned | `goose`、`roo`、`lmstudio`、`copilot`、`kilo`、`zed`、`qoder`、`anythingllm`、`devin`、`mimo`、`zcode` | 不再使用通用 SQLite 猜测；显式启用时返回所需专用 reader |

例如：

```bash
tokenbar status --providers claude,kimi,gemini,pi
```

对其他 CLI，可以通过 `AI_CLI_STATUSLINE_SOURCES` 提供只读日志根目录：

```bash
export AI_CLI_STATUSLINE_SOURCES='{"my-cli":["~/.my-cli/sessions"]}'
tokenbar status --providers my-cli
```

通用 JSONL 解析器识别 `usage`、`input_tokens`／`output_tokens` 或 `prompt_tokens`／`completion_tokens` 字段，但只属于 experimental；为避免 `watch` 被长日志阻塞，每个文件默认只读取末尾 8 MiB。SQLite reader 不再按列名猜测，只允许 provider 专用 schema 中明确列出的表和字段。完整矩阵见 [Provider 支持审计](docs/provider-support-audit.md) 。

## 数据和隐私

- 只读取本机 CLI 的状态数据库、会话日志或只读 app-server 接口。
- 不读取、打印或提交 API key、OAuth 凭据和认证文件内容。
- 不输出完整提示词、完整回复或会话正文。
- SQLite reader 使用只读连接、`PRAGMA query_only=ON` 和正向字段白名单；不会查询 `access_token`、`refresh_token` 或 `token_expiry`。
- 状态栏缓存按字段合并，默认 24 小时后显式标记过期；可用 `AI_CLI_STATUSLINE_CACHE_TTL_SECONDS` 调整。
- 未安装 CLI 或没有可识别日志时显示 unavailable。

## 验证

```bash
PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q
```

当前离线测试覆盖凭据字段隔离、Codex 部分失败和多数据库回退、8 MiB JSONL 尾部读取限制、缓存合并／过期／并发写入、OpenCode 专用 schema、未知 provider 和 stdin 状态栏协议。本机已安装 Kimi Code 2.0.0，但没有可识别会话且尚未配置 `status_line`，因此真实 `/reload-tui` 仍未验证；Codex app-server 实时额度也受当前沙箱限制，不能用离线测试冒充实机成功。

## 看不到数据时

1. 先运行 `tokenbar status --json --no-color`，确认具体 provider 的 `source` 和 `error`。
2. Claude Code 检查 `~/.claude/projects/` 是否有新的 JSONL 会话。
3. Kimi Code 检查 `~/.kimi-code/sessions/` 是否有 `wire.jsonl`；旧版目录是 `~/.kimi/`。
4. 如果使用自定义目录，设置 `CLAUDE_CONFIG_DIR`、`KIMI_CODE_HOME` 或 `AI_CLI_STATUSLINE_SOURCES`。
5. 账户限额只会在 CLI 的 status-line 快照或官方只读接口返回时显示，不会根据 token 数量猜测额度。

### 常见安装和 Kimi 问题

- **`externally-managed-environment`**：这是 Homebrew Python 的 PEP 668 保护。请在项目目录创建并使用虚拟环境，不要加 `--break-system-packages`：

  ```bash
  python3 -m venv .venv
  .venv/bin/python -m pip install -e .
  .venv/bin/tokenbar status --providers kimi
  ```

- **`tokenbar: command not found`**：当前 shell 没有使用项目虚拟环境。执行 `source .venv/bin/activate` 后用 `command -v python3` 和 `command -v tokenbar` 检查路径是否包含 `.venv/bin/`；也可以直接使用 `.venv/bin/tokenbar`。
- **`python: aliased to python3`**：这是 zsh 的普通 alias，不是安装错误。关键是 `python3` 的实际路径必须是 `.venv/bin/python3`；为避免 alias 和 PATH 混淆，可始终使用 `.venv/bin/python`。
- **`setup kimi` 提示已有 `[status_line]`**：工具默认不会覆盖现有配置。确认要替换时执行 `tokenbar setup kimi --force`；原文件会先备份为 `tui.toml.bak`，然后在 Kimi 中执行 `/reload-tui`。
- **手动运行 `tokenbar kimi-statusline` 一直等待**：该命令是 Kimi 的 stdin 回调，不是交互式查询命令。不要单独运行；配置完成后由 Kimi 自动调用。当前版本在终端中直接运行会立即返回，不再无限等待输入。
- **Kimi 显示“未找到可识别 token 字段”**：检查 `wire.jsonl` 是否包含 `usage`。Kimi Code 原生 `usage.record` 的 `inputOther`、`output`、`inputCacheRead` 和 `inputCacheCreation` 已支持；如果日志字段完全不同，请提供字段名而不要发送会话正文。

## 项目状态

当前进度和未完成事项见 [ROADMAP.md](ROADMAP.md)。开源发布、远程推送和生产部署不属于本地项目默认操作。

## 许可证

[MIT License](LICENSE)
