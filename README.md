# ai-cli-statusline

本项目是一个本地优先、只读的多 AI CLI 用量状态栏工具，目标是把 Codex、Claude Code、Kimi Code 的 token、上下文和额度信息统一成一行 ANSI 状态栏或 JSON 输出。

## 当前能力

- Codex：通过 `codex app-server --stdio` 读取账户额度，通过 `$CODEX_HOME/state_5.sqlite` 只读读取最近会话 token 和模型。
- Claude Code：扫描 `~/.claude/projects` 下最新 JSON/JSONL 会话，汇总可识别的 `usage` 字段。
- Kimi Code：扫描 `~/.kimi` 和 `~/.config/kimi`，字段规则与 Claude 类似，也可用 `KIMI_CONFIG_DIR` 指定目录。
- 终端：一次性 `status`、持续 `watch`、`--no-color` 和 JSON 输出。

Kimi CLI 当前未安装，Claude 本机日志也没有发现可用于账户级额度的稳定接口。因此 Kimi 适配器和 Claude 的账户额度显示仍属于待真实环境验证范围，不会伪造数据。

## 安装与运行

项目只依赖 Python 标准库。开发环境运行：

```bash
cd ai-cli-statusline
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

查看一次状态：

```bash
ai-cli-statusline status --providers codex,claude,kimi
```

持续刷新：

```bash
ai-cli-statusline watch --providers codex,claude,kimi --interval 10
```

脚本化读取：

```bash
ai-cli-statusline status --json --no-color
```

也可以不安装，直接从源码运行：

```bash
PYTHONPATH=src python3 -m ai_cli_statusline watch --providers codex,claude,kimi
```

## 接入三个原生 CLI

安装后可生成各 CLI 的接入配置说明：

```bash
ai-cli-statusline integrate claude
ai-cli-statusline integrate kimi
ai-cli-statusline integrate codex
```

- Claude Code：使用官方 `statusLine` 命令协议。将 `claude-statusline` 配置到 `~/.claude/settings.json`，Claude 会把会话 JSON 通过 stdin 传入，底部状态栏可显示上下文进度条和 5 小时／7 天额度。
- Kimi Code：使用官方 `~/.kimi-code/tui.toml` 的 `[status_line].command` 协议；旧版 Kimi 的配置目录可能是 `~/.kimi`。修改后执行 `/reload-tui`。
- Codex：官方底部栏目前只支持内置 `tui.status_line` 项目，不支持外部命令回调。因此保留原生 token／上下文／额度项目，并用 Stop Hook 输出本工具的彩色摘要；需要持续刷新时使用 `watch` 旁路终端。

`claude-statusline` 和 `kimi-statusline` 都是无状态 stdin 适配器，可直接用模拟 JSON 验证：

```bash
printf '%s\n' '{"model":{"display_name":"Claude"},"context_window":{"used_percentage":25,"context_window_size":200000}}' \
  | ai-cli-statusline claude-statusline
```

## 输出示例

```text
Codex gpt-5.6-sol · total 25.6k · in 25.5k / out 6 · 5h ████░░░░░░ 36% used  │  Claude unavailable (日志中没有可识别 token 字段)  │  Kimi unavailable (未找到 Kimi 会话日志)
```

进度条显示“已用额度的剩余比例”，因此 `████░░░░░░ 36% used` 表示 5 小时额度已使用 36%，而不是任务完成百分比。

## 隐私和安全边界

- 不读取 `auth.json`、API key 或环境变量中的 secret 内容。
- Codex app-server 只请求 `account/rateLimits/read`，本地 SQLite 使用 `mode=ro` 与 `PRAGMA query_only=ON`。
- Claude/Kimi 只读取日志末尾的有限字节，并只提取 token、模型和上下文数值，不输出消息正文。
- 未提交真实日志、数据库、凭据或本地使用聚合数据。

## Codex 集成说明

Codex 原生 `tui.status_line` 仍然由 Codex 自己绘制；本项目是外部监控器，适合放在 tmux 旁路、独立终端或脚本输出中。它不会修改 Codex 的 TUI，也不会把外部进度条冒充为原生底部状态栏。

当前机器上已有的 Codex Stop Hook（`/Users/annelo/.codex/hooks/codex_terminal_summary.py`）是“每轮完成后摘要”；本项目的 `watch` 是“定时轮询外部状态”。两者可以并存。

## 验证

```bash
python3 -m pytest
```

离线测试覆盖进度条边界、统一渲染、嵌套 usage 汇总和 Kimi 可配置目录。真实 Codex 额度读取需要登录状态和正在运行的本机 CLI；真实 Claude/Kimi 读取需要对应会话日志。

## 计划

见 [ROADMAP.md](ROADMAP.md)。开源发布、提交和推送均需单独执行，不在本地 MVP 中自动进行。
