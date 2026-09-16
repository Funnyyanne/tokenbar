# tokenbar

本地优先的多 AI CLI 用量状态栏工具，为 Codex、Claude Code 和 Kimi Code 提供统一的 token、上下文和额度展示。

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
- 其他工具：内置 Gemini、Pi、OMP、OmO、Goose 的 JSONL，以及 Cursor、OpenCode、Copilot、Kilo、Zed、Qoder 的只读 SQLite 入口，也可通过环境变量添加自定义日志目录。
- 进度条使用 `█` 和 `░`，额度百分比明确标注为已用比例。

## 安装

需要 Python 3.10 或更高版本；项目只使用 Python 标准库。

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

使用 `auto` 可以一次检查所有内置平台：

```bash
tokenbar status --providers auto
```

内置 provider 和数据来源：

| provider | 本地来源 | 读取方式 |
| --- | --- | --- |
| `codex` | app-server、`state_5.sqlite` | 官方只读 RPC + SQLite |
| `claude` | `~/.claude/projects/**/*.jsonl` | JSONL + statusLine 缓存 |
| `kimi` | `~/.kimi-code/**/wire.jsonl` | wire JSONL + status_line 缓存 |
| `gemini`、`antigravity`、`deepseek`、`pi`、`omp`、`omo`、`goose`、`craft`、`reasonix`、`roo`、`lmstudio` | 各自会话／日志 JSONL 目录 | 通用 JSONL |
| `cursor`、`opencode`、`copilot`、`kilo`、`zed`、`qoder`、`anythingllm`、`devin`、`mimo`、`zcode` | 常见本地 SQLite 目录 | 只读 SQLite token 字段 |

例如：

```bash
tokenbar status --providers claude,kimi,gemini,pi
```

对其他 CLI，可以通过 `AI_CLI_STATUSLINE_SOURCES` 提供只读日志根目录：

```bash
export AI_CLI_STATUSLINE_SOURCES='{"my-cli":["~/.my-cli/sessions"]}'
tokenbar status --providers my-cli
```

通用 JSONL 解析器识别 `usage`、`input_tokens`／`output_tokens` 或 `prompt_tokens`／`completion_tokens` 字段。SQLite reader 只读取名称包含 token、input、output、prompt、completion、cache 的数值列。

## 数据和隐私

- 只读取本机 CLI 的状态数据库、会话日志或只读 app-server 接口。
- 不读取、打印或提交 API key、OAuth 凭据和认证文件内容。
- 不输出完整提示词、完整回复或会话正文。
- Codex SQLite 使用只读连接和 `PRAGMA query_only=ON`。
- 未安装 CLI 或没有可识别日志时显示 unavailable。

## 验证

```bash
PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q
```

当前离线测试覆盖进度条边界、统一渲染、嵌套 usage 汇总、可配置日志目录和 stdin 状态栏协议。当前机器已验证 Claude 命令存在；Kimi CLI 未安装，因此 Kimi TUI 尚未完成实机验证。

## 看不到数据时

1. 先运行 `tokenbar status --json --no-color`，确认具体 provider 的 `source` 和 `error`。
2. Claude Code 检查 `~/.claude/projects/` 是否有新的 JSONL 会话。
3. Kimi Code 检查 `~/.kimi-code/sessions/` 是否有 `wire.jsonl`；旧版目录是 `~/.kimi/`。
4. 如果使用自定义目录，设置 `CLAUDE_CONFIG_DIR`、`KIMI_CODE_HOME` 或 `AI_CLI_STATUSLINE_SOURCES`。
5. 账户限额只会在 CLI 的 status-line 快照或官方只读接口返回时显示，不会根据 token 数量猜测额度。

## 项目状态

当前进度和未完成事项见 [ROADMAP.md](ROADMAP.md)。开源发布、远程推送和生产部署不属于本地项目默认操作。

## 许可证

[MIT License](LICENSE)
