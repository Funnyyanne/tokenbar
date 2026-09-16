# ai-cli-statusline

本地优先的多 AI CLI 用量状态栏工具，为 Codex、Claude Code 和 Kimi Code 提供统一的 token、上下文和额度展示。

[English README](README.en.md)

## 特性

- 统一 ANSI 状态栏和 JSON 输出。
- 支持一次性查询 `status` 和持续刷新 `watch`。
- Codex：通过 `codex app-server --stdio` 读取账户额度，并以只读方式读取本地会话 token 和模型。
- Claude Code：扫描本地会话日志，也支持 Claude 官方 `statusLine` stdin 协议。
- Kimi Code：扫描可配置的本地会话目录，也支持 Kimi 官方 `[status_line].command` stdin 协议。
- 进度条使用 `█` 和 `░`，额度百分比明确标注为已用比例。

## 安装

需要 Python 3.10 或更高版本；项目只使用 Python 标准库。

```bash
cd ai-cli-statusline
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

也可以直接从源码运行：

```bash
PYTHONPATH=src /usr/local/bin/python3.11 -m ai_cli_statusline status --no-color
```

## 使用

查看一次状态：

```bash
ai-cli-statusline status --providers codex,claude,kimi
```

持续刷新：

```bash
ai-cli-statusline watch --providers codex,claude,kimi --interval 10
```

输出机器可读 JSON：

```bash
ai-cli-statusline status --json --no-color
```

`--providers` 接受逗号分隔的 `codex`、`claude`、`kimi`。单个 provider 不可用时会显示 unavailable，不会伪造数据。

## 接入原生 CLI

先查看对应配置说明：

```bash
ai-cli-statusline integrate claude
ai-cli-statusline integrate kimi
ai-cli-statusline integrate codex
```

### Claude Code

Claude Code 的 `statusLine` 命令会从 stdin 接收会话 JSON，并把脚本 stdout 显示在底部状态栏。将 `integrate claude` 输出的配置合并到 `~/.claude/settings.json`：

```json
{
  "statusLine": {
    "type": "command",
    "command": "ai-cli-statusline claude-statusline",
    "refreshInterval": 5
  }
}
```

测试适配器：

```bash
printf '%s\n' '{"model":{"display_name":"Sonnet"},"context_window":{"used_percentage":25,"context_window_size":200000}}' \
  | ai-cli-statusline claude-statusline
```

### Kimi Code

新版 Kimi Code 使用 `~/.kimi-code/tui.toml`；旧版可能使用 `~/.kimi/tui.toml`。加入：

```toml
[status_line]
command = "ai-cli-statusline kimi-statusline"
```

修改后在 Kimi 中执行 `/reload-tui`。Kimi 的自定义状态栏命令有执行时间限制，命令应保持轻量。

### Codex

Codex 原生底部栏目前使用内置 `tui.status_line` 项目，不提供外部命令回调。因此本工具采用两层方式：

1. 保留 Codex 原生的 token、上下文和额度字段。
2. 使用 Stop Hook 输出彩色用量摘要；需要持续刷新时运行本工具的 `watch`。

本项目不会把外部输出冒充成 Codex 原生 TUI 底部栏。

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

## 项目状态

当前进度和未完成事项见 [ROADMAP.md](ROADMAP.md)。开源发布、远程推送和生产部署不属于本地项目默认操作。

## 许可证

[MIT License](LICENSE)
