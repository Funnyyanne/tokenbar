# tokenbar

本地优先的多 AI CLI 用量状态栏工具，在终端展示可读取的 token、上下文占用和账户额度。进度只使用来源明确提供的百分比或占用量／容量，不根据 token 总数猜测。

[English README](README.en.md)

主命令是 `tokenbar`；旧命令 `ai-cli-statusline` 仍作为兼容别名保留。

![终端状态栏效果演示](docs/demo-statusline.svg)

> 图片为演示输出，数值为模拟数据，不代表真实账户额度。

## 快速导航

- [安装与快速开始](#安装)
- [终端命令与输出说明](#使用)
- [Claude／Kimi 原生状态栏](#接入原生-cli)
- [Provider 与数据来源](#其他-cli-和自定义日志)
- [环境变量](#环境变量)
- [排查 unavailable 和安装问题](#看不到数据时)
- [开发验证与项目文档](#开发与验证)

## 当前能力

当前登记 44 个 provider：4 个 stable、35 个 experimental、5 个 planned，其中 38 个 reader 能识别明确的用量格式。`stable` 表示 reader／协议成熟度，不保证本机已安装 CLI 或存在有效会话。`experimental` 需要显式选择；`planned` 和受限项在默认来源下返回 unavailable。单个平台不可用不会阻断其他平台。

你可以在独立终端中用 `status`／`watch` 查看多个 CLI 的用量，也可以将 Claude Code、Kimi Code 的 stdin 回调接入它们的原生底栏。

| 平台 | Token 来源 | 上下文进度 | 账户额度进度 |
| --- | --- | --- | --- |
| Codex | 本地只读 SQLite | 当前 reader 不提供 | app-server 只读接口，失败时保留本地 token 并显示错误 |
| Claude Code | 本地会话日志、官方 stdin 回调 | 官方 stdin 回调 | stdin 中提供额度窗口时显示 |
| Kimi Code | 本地 `wire.jsonl` | 官方 stdin 的 `contextTokens`／`maxContextTokens` | 当前无专用额度来源 |
| OpenCode | 本地只读 SQLite | 当前 reader 不提供 | 当前 reader 不提供 |

平台登记数与可读取格式数不等于实机支持数量。具体来源、版本限制和验证边界见 [Provider 支持审计](docs/provider-support-audit.md) 和 [TokenTracker 工具覆盖表](docs/terminal-cli-coverage.md) 。

## 特性

- 统一 ANSI 状态栏和 JSON 输出。
- 支持一次性查询 `status` 和持续刷新 `watch`。
- Codex：通过 `codex app-server --stdio` 读取账户额度，并以只读方式读取本地会话 token 和模型。
- Claude Code：扫描本地会话日志，也支持 Claude 官方 `statusLine` stdin 协议。
- Kimi Code：扫描 `wire.jsonl` 和可配置的本地会话目录，也支持 Kimi 官方 `[status_line].command` stdin 协议。
- OpenCode：通过正向白名单读取新版 `session.tokens_*`；旧版在 SQLite 内仅提取明确的 token／model 路径，不将消息正文返回 Python。
- 其他工具按 stable、experimental、planned 分级；`auto` 只启用有专用 reader 和回归证据的 stable provider。
- 进度条使用 `█` 和 `░`，额度百分比明确标注为已用比例。
- `watch` 按平台分行并按终端宽度折行；支持无颜色重绘，Ctrl-C 或 SIGTERM 退出时恢复原屏幕与光标。
- 来源提供额度重置时间时显示倒计时；无百分比或分母时不推算进度。

## 安装

需要 Python 3.10 或更高版本，以及目标 CLI 已产生的本地会话或状态栏回调。安装会自动获取 `zstandard`（用于 DeepSeek Harness 压缩日志）；Python 3.10 还会安装 `tomli`。

以下为源码安装方式。在含 `pyproject.toml` 的项目根目录执行，先确认 Python 版本。

### macOS／Linux

先用 `python3 --version` 确认版本。若系统 `python3` 低于 3.10，但已安装 Python 3.11，使用 `python3.11 -m venv .venv` 创建虚拟环境，再按下面的步骤激活和安装。

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
tokenbar --version
```

若系统 `python3` 低于 3.10，但已安装 Python 3.11，将创建环境的命令改为 `python3.11 -m venv .venv`。后续打开新终端时，重新激活 `.venv`，或直接运行 `.venv/bin/tokenbar`。

### Windows PowerShell

确认 `py -3 --version` 输出为 Python 3.10 或更高版本；以下命令直接调用虚拟环境中的程序，无需激活。

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\tokenbar.exe --version
.\.venv\Scripts\tokenbar.exe status --providers auto --no-color
```

后续示例使用 macOS／Linux shell；Windows 中可将 `tokenbar` 替换为 `.\.venv\Scripts\tokenbar.exe`。各平台的实际 reader 与终端验证范围见 [覆盖表](docs/terminal-cli-coverage.md) 。

### 快速开始

```bash
# 查看四个 stable provider
tokenbar status --providers auto

# 每 5 秒刷新一次，Ctrl-C 退出
tokenbar watch --providers auto --interval 5

# 输出机器可读 JSON
tokenbar status --providers auto --json --no-color
```

`auto` 包含 `codex`、`claude`、`kimi`、`opencode`。只使用一个工具时，直接指定它：

```bash
tokenbar status --providers claude
tokenbar status --providers kimi
```

完成依赖安装后，也可以通过模块入口运行：

```bash
python3 -m ai_cli_statusline status --providers auto --no-color
```

仅设置源码路径不会安装依赖。已准备好依赖、但尚未安装项目时，可使用：

```bash
PYTHONPATH=src python3 -m ai_cli_statusline status --providers auto --no-color
```

## 使用

### 命令与参数

| 命令 | 用途 |
| --- | --- |
| `tokenbar status` | 查看一次状态；省略子命令时也执行 `status` |
| `tokenbar watch` | 持续刷新，每个平台分行显示 |
| `tokenbar integrate claude\|kimi\|codex` | 打印集成说明，不修改配置；Codex 提供独立终端的使用说明 |
| `tokenbar setup claude\|kimi` | 写入对应宿主配置；现有配置默认不覆盖 |
| `tokenbar claude-statusline`、`tokenbar kimi-statusline` | 由宿主通过 stdin JSON 调用并输出状态栏 |

| 参数 | 默认值／作用 |
| --- | --- |
| `--providers` | 默认 `codex,claude,kimi`；接受逗号分隔名称、`auto` 或 `all` |
| `--interval` | 默认 10 秒，最小 2 秒；用于 `watch` |
| `--json` | 输出 JSON；`watch` 每次刷新输出一行 JSON 数组 |
| `--no-color` | 关闭颜色；在可控制终端中仍保留 `watch` 重绘 |
| `--theme` | 默认 `catppuccin-mocha`；也支持 `nord`、`dracula`、`default` |
| `--progress-style` | 默认 `blocks`；也支持 `ascii`、`thin`、`dots` |
| `--force` | `setup` 覆盖已有状态栏配置，并备份现有文件 |
| `--help`、`--version` | 查看命令帮助或当前版本 |

不传 `--providers` 时默认检查 Codex、Claude、Kimi；需要包括 OpenCode 时使用 `auto`。`all` 选择全部登记项，包含 experimental、planned 和受限项，不表示所有平台都有可用数据。只要有一项当前数据，`status` 就返回 0；应逐项查看错误，而不能仅凭退出码判断全部可用。

### 一次查询与持续刷新

查看一次状态：

```bash
tokenbar status --providers codex,claude,kimi
```

持续刷新：

```bash
tokenbar watch --providers codex,claude,kimi --interval 10
```

按自己使用的 CLI 缩小 provider 范围，可以减少无数据提示和不必要的查询。`watch` 在可控制终端使用独立屏幕，退出后恢复；`--no-color` 和 `NO_COLOR` 只关闭颜色。重定向、`--json` 或 `TERM=dumb` 使用追加输出，不发送屏幕控制码。`status` 与原生 stdin 状态栏保持一行输出。

Ctrl-C 退出码为 0，SIGTERM（普通 `kill`）退出码为 143；两者都经过终端清理。无效 provider 名称会在原屏幕显示错误并以退出码 2 结束。

### 如何理解数字

`ctx` 表示上下文已用比例，`5h`／`7d` 表示账户额度已用比例；token 总数不能当作这两者的进度。无可靠来源时只显示 token 或 unavailable。`reset in` 来自上游重置时间；`reset due` 表示已到期且仍等待新的额度快照，不会自动将已用比例改为 0。

不同 reader 的统计跨度不同：有的显示最新会话，有的读取数据库汇总，LM Studio 会合并轮转日志。多个 provider 的 token 不应直接相加当作全账户账单。只有上下文数据而没有累计 token 时，仍可显示 `ctx`。

### 主题与进度条

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

### JSON 与退出码

输出机器可读 JSON：

```bash
tokenbar status --json --no-color
```

需要连续采集 JSON 时运行 `tokenbar watch --providers auto --json --interval 5`；每次刷新输出一行 JSON 数组，适合逐行读取。

| JSON 字段 | 含义 |
| --- | --- |
| `provider`、`maturity` | 平台标识与 reader 成熟度 |
| `model`、`tokens`、`input_tokens`、`output_tokens` | 当前来源提供的模型和 token 统计；无对应值时为 `null` |
| `context_used`、`context_window` | 上下文占用量与容量，不是累计计费用量 |
| `rate_limits` | 额度窗口列表；为空表示没有返回窗口；`used_percent` 是已用百分比，`resets_at` 是 Unix 秒时间戳 |
| `source`、`error` | 来源路径／接口与错误说明；无错误时 `error` 为 `null` |
| `updated_at`、`stale` | 快照时间与是否过期；回调缓存过期时 `stale` 为 `true` |

| 退出码 | 含义 |
| --- | --- |
| `0` | `status` 至少有一项当前数据，或 `watch` 通过 Ctrl-C 正常退出 |
| `1` | `status` 没有当前可用数据 |
| `2` | 参数或 provider 名称无效 |
| `143` | `watch` 收到 SIGTERM，并完成退出清理 |

需要连续采集 JSON 时运行 `tokenbar watch --providers auto --json --interval 5`；每次刷新输出一行 JSON 数组，适合逐行读取。

| 退出码 | 含义 |
| --- | --- |
| `0` | `status` 至少有一项当前数据，或 `watch` 通过 Ctrl-C 正常退出 |
| `1` | `status` 没有当前可用数据 |
| `2` | 参数或 provider 名称无效 |
| `143` | `watch` 收到 SIGTERM，并完成退出清理 |

## 接入原生 CLI

`integrate` 只打印说明，`setup` 才写入宿主配置。自动配置仅支持 Claude 和 Kimi；Codex 使用独立终端中的 `watch`。

先查看说明，再选择需要自动配置的宿主：

```bash
tokenbar integrate claude
tokenbar integrate kimi
tokenbar integrate codex

# 自动写入配置；已有配置默认不覆盖
tokenbar setup claude
tokenbar setup kimi
```

宿主需要能找到配置中的可执行文件。如果宿主启动时没有激活项目虚拟环境，可在手动配置中使用 `tokenbar` 的绝对路径，例如 `/absolute/path/to/tokenbar/.venv/bin/tokenbar`。路径包含空格时需要保留 shell 引号：

```json
{
  "statusLine": {
    "type": "command",
    "command": "\"/absolute/path with spaces/tokenbar/.venv/bin/tokenbar\" claude-statusline"
  }
}
```

Kimi 的 TOML `command` 同样需要指向宿主可以执行的命令。

### Claude Code

Claude Code 的 `statusLine` 命令会从 stdin 接收会话 JSON，并把脚本 stdout 显示在底部状态栏；`refreshInterval` 可用于定时刷新。配置协议见 [Claude 官方文档](https://code.claude.com/docs/en/statusline) 。将 `integrate claude` 输出的配置合并到 `~/.claude/settings.json`：

```json
{
  "statusLine": {
    "type": "command",
    "command": "tokenbar claude-statusline",
    "refreshInterval": 5
  }
}
```

可用模拟输入检查输出：

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

修改后在 Kimi 中执行 `/reload-tui`；也可以重启 Kimi。官方协议限制自定义命令执行时间为 300 ms，命令应保持轻量。配置与重载说明见 [Kimi 官方文档](https://www.kimi.com/code/docs/en/kimi-code-cli/configuration/config-files.html) 。

Kimi 的官方 stdin 协议使用 `contextTokens` 和 `maxContextTokens`，本工具据此显示上下文进度；该占用量不作为累计 token 或账户额度。Claude 的上下文回退统计包含输入、缓存创建和缓存读取 token。两种回调均接受 `--no-color`、`--theme` 和 `--progress-style`。

可用模拟输入检查回调输出：

```bash
printf '%s\n' '{"model":"kimi-k2","contextTokens":102400,"maxContextTokens":204800}' \
  | tokenbar kimi-statusline --no-color --progress-style ascii
```

预期输出为 `Kimi · kimi-k2 · ctx #####..... 50% used`。该示例只演示输入格式和渲染效果，不代表真实会话或账户额度。

已有配置文件时，`setup` 会先创建 `.bak` 备份；新文件没有可备份内容。已有 `[status_line]` 或 Claude `statusLine` 时默认停止，需要覆盖时才使用 `--force`。

### Codex

Codex 原生底部栏使用内置 `tui.status_line` 项目；本工具没有向该底部栏注入外部命令的配置入口。使用方式：

1. 保留 Codex 原生的 token、上下文和额度字段。
2. 在单独终端运行 `tokenbar watch --providers codex --interval 5`，持续显示本地 token 和可读取的账户额度。

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
| stable（进入 `auto`） | `opencode` | 新版 `session.tokens_*`；旧版用 SQLite `json_extract` 仅读取 `message.data` 的 usage 路径 |
| experimental（仅显式启用） | `cursor` | CLI 的可靠本地用量来源尚未确认；专用受限 adapter 返回 unavailable，不读取 auth token |
| experimental（仅显式启用） | `gemini`、`pi` | 分别读取 Gemini 保存会话的 `messages[].tokens`，以及 Pi assistant message 的 `usage` |
| experimental（仅显式启用） | `omp`、`omo` | 汇总最新有效主／子会话树的 assistant usage，同 ID 修正替换；OMP reasoningTokens 独立计，OmO reasoning 已含在 output 中 |
| experimental（仅显式启用） | `goose`、`roo`、`copilot`、`kilo`、`zed`、`anythingllm`、`devin`、`zcode` | Copilot 优先原生数据库，回退 OTel；Devin 按全局 request_id 去重；ZCode 合并迁移前历史并排除镜像；Zed 仅支持未压缩旧线程 |
| experimental（仅显式启用） | `codebuddy` | `projects/**/*.jsonl` 中的 `providerData.rawUsage`；按响应 ID 去重，input／output 已含缓存／reasoning |
| experimental（仅显式启用） | `workbuddy` | 最新主／子会话树的 rawUsage；同会话明细优先，缺明细时回退 `traces/**/trace_*.json` 的明确总量，不叠加缓存或 trace 镜像 |
| experimental（仅显式启用） | `dots`、`prime`、`minimax` | 专用会话 usage；Dots 按 Pi 的 `provider=dots` 分流，Pi 不重复显示 Dots；MiniMax 只读 `messages.jsonl` |
| experimental（仅显式启用） | `astudio`、`everycode` | `.acode`／`.code` 的 Codex 格式 rollout，显示最新累计 token 快照，不累加累计事件 |
| experimental（仅显式启用） | `commandcode`、`reasonix`、`openclaw`、`droid`、`cline` | 分别读取明确的消息 usage、telemetry sidecar、assistant usage、settings tokenUsage 和 Cline CLI v3 metrics |
| experimental（仅显式启用） | `hermes`、`claudescience`、`mimo` | SQLite 白名单元数据；Claude Science 排除示例正文，MiMo 排除非原生 provider 的镜像消息 |
| experimental（仅显式启用） | `qoder`、`qodercn` | `.qoder/projects`／`.qoder-cn/projects` 的 assistant message usage；credits 不计为 token；不读 GUI 数据库 |
| experimental（仅显式启用） | `grok`、`deepseek`、`lmstudio` | Grok turn_completed usage（模型明细不完整时回退到有效顶层用量）、DeepSeek Harness v0／v3 JSONL（含多帧 zstd）、LM Studio 最终响应日志；忽略上下文估算，按事件／响应 ID 去重 |
| experimental（仅显式启用） | `antigravity`、`kiro` | Antigravity generation metadata 对应已完成 planner 的明确 token；Kiro 仅支持旧 CLI 会话 input_token_count／output_token_count，新版字符／credits 不计 token |
| planned／受限 | `craft`、`kilocode`、`unsloth`、`trae`、`traecn` | 尚无专用 reader，显式调用返回原因；Kilo Code 扩展与 Kilo CLI 是不同来源 |

查看全部登记项，或只选择已经接入的 CLI：

```bash
tokenbar status --providers all --json --no-color
tokenbar watch --providers codebuddy,workbuddy,omo,prime,minimax,commandcode,cline --interval 5
```

新增 JSON reader 通过 SQLite JSON 投影仅读取固定的标量元数据，Python 不解码提示词或回复对象；每次刷新重建统计，日志截断／重写不会叠加上次计数。会话 reader 选择最新有效来源；WorkBuddy／OMP／OmO 汇总同一逻辑会话的子代理，LM Studio 合并轮转日志并对响应去重。DeepSeek 压缩日志使用安装时自动提供的 `zstandard` 依赖。它们没有独立账户额度来源。完整平台映射与支持范围见 [覆盖表](docs/terminal-cli-coverage.md) 。

例如：

```bash
tokenbar status --providers claude,kimi,gemini,pi
```

Copilot CLI 优先读取 `~/.copilot/session-store.db` 的原生 assistant 用量表，input／output 已包含缓存／reasoning。原生表存在但没有完整用量时显示 unavailable；原生格式不可识别时才回退 OTel，不合并镜像。文件导出与内容捕获选项见 [Copilot 官方文档](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#opentelemetry-monitoring) 。使用文件导出时，先设置环境变量并运行 Copilot，在另一个继承相同变量的终端查询，或结束 Copilot 后查询：

```bash
mkdir -p "$HOME/.copilot/otel"
export COPILOT_OTEL_FILE_EXPORTER_PATH="$HOME/.copilot/otel/copilot.jsonl"
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false
copilot
tokenbar status --providers copilot
```

### 自定义来源

对其他 CLI，可以通过 `AI_CLI_STATUSLINE_SOURCES` 提供只读日志根目录：

Gemini、Pi 和 OMP 的专用 reader 也接受此配置，优先读取配置目录；日志仍需符合各 provider 的支持格式。

```bash
export AI_CLI_STATUSLINE_SOURCES='{"my-cli":["~/.my-cli/sessions"]}'
tokenbar status --providers my-cli
```

为已接入的 provider 配置目录时，同样可使用 `AI_CLI_STATUSLINE_SOURCES`，保留该 provider 的专用格式解析，例如 `{"minimax":["/absolute/path/to/sessions"]}`。目录应指向会话／数据根；Codex 使用 `CODEX_HOME`，Cursor 的隐私限制不通过自定义目录绕过。

未知 provider 使用 experimental 通用 JSONL reader。建议目录内只存放用量元数据；每行写一个独立用量记录，例如：

```json
{"model":"my-model","usage":{"input_tokens":100,"output_tokens":20}}
```

通用 reader 识别 `usage`、`input_tokens`／`output_tokens` 或 `prompt_tokens`／`completion_tokens`，但不处理专用 provider 的响应去重、镜像或累计快照语义。通用 reader、Claude 与 Kimi 的文件读取默认限于末尾 8 MiB；新增专用 JSONL reader 从头流读，具体范围见 [覆盖表](docs/terminal-cli-coverage.md) 。SQLite 仅读取 provider 专用 schema 白名单，不能通过自定义目录让未知数据库自动获得支持。

## 环境变量

| 变量 | 用途／默认值 |
| --- | --- |
| `CODEX_HOME` | Codex 数据根，默认 `~/.codex` |
| `CLAUDE_CONFIG_DIR` | Claude 配置根，默认 `~/.claude`；reader 扫描其 `projects`，`setup claude` 写入其 `settings.json` |
| `KIMI_CODE_HOME` | Kimi 数据／配置根；设置后 reader 只扫描该目录，`setup kimi` 写入其 `tui.toml`；未设置时 reader 也尝试旧版目录 |
| `AI_CLI_STATUSLINE_SOURCES` | JSON 对象：provider 名称映射到目录数组；为已接入项保留专用解析，为自定义项使用通用 JSONL reader |
| `AI_CLI_STATUSLINE_HOME` | tokenbar 回调缓存根，默认 `~/.ai-cli-statusline`；快照位于 `cache/<provider>.json` |
| `AI_CLI_STATUSLINE_CACHE_TTL_SECONDS` | 回调缓存有效期，默认 86400 秒（24 小时） |
| `AI_CLI_STATUSLINE_THEME` | 默认主题；命令行 `--theme` 优先 |
| `AI_CLI_STATUSLINE_PROGRESS_STYLE` | 默认进度样式；命令行 `--progress-style` 优先 |
| `NO_COLOR` | 存在时关闭颜色，值可以为空；不关闭 TTY 下的 `watch` 重绘 |

缓存保存状态栏回调的元数据，供没有有效会话日志时回退；它不是账单历史。Claude／Kimi 回调会写入缓存，`status`／`watch` 读取 CLI 来源时不修改这些来源。其他 reader 的专用目录变量见 [覆盖表](docs/terminal-cli-coverage.md) 。

## 数据和隐私

- 只读取本机 CLI 的状态数据库、会话日志或只读 app-server 接口。
- 不读取、打印或提交 API key、OAuth 凭据和认证文件内容。
- 不输出完整提示词、完整回复或会话正文。
- SQLite reader 使用只读连接、`PRAGMA query_only=ON` 和正向字段白名单；不会查询 `access_token`、`refresh_token` 或 `token_expiry`。
- 状态栏缓存按字段合并，默认 24 小时后显式标记过期；可用 `AI_CLI_STATUSLINE_CACHE_TTL_SECONDS` 调整。
- 没有可识别日志、有效回调缓存或可用接口时显示 unavailable。

## 开发与验证

在项目根目录的已激活虚拟环境中安装项目与测试依赖，再运行检查：

```bash
python3 -m pip install -e . pytest
python3 -m pytest -q
python3 -m compileall -q src tests
```

测试覆盖字段白名单、缓存合并／过期／并发写入、专用来源、消息去重／修正、错误输入、压缩日志、stdin 协议与 POSIX PTY 下的刷新和退出恢复。离线 fixture 不证明目标 CLI 版本或真实宿主可用。

| 目录／文件 | 用途 |
| --- | --- |
| `src/ai_cli_statusline/adapters/` | 各 provider 的只读 reader |
| `src/ai_cli_statusline/cli.py` | 命令入口、provider 选择和刷新循环 |
| `src/ai_cli_statusline/integrations.py` | stdin 回调及 Claude／Kimi 配置写入 |
| `src/ai_cli_statusline/render.py`、`cache.py` | 终端渲染和回调缓存 |
| `tests/` | 离线 reader、协议、缓存与终端回归 |

更多项目文档：

- [AGENTS.md](AGENTS.md)：工程边界与验证入口。
- [Provider 支持审计](docs/provider-support-audit.md)：成熟度与隐私约束。
- [工具覆盖表](docs/terminal-cli-coverage.md)：逐平台来源与版本限制。
- [终端验证报告](docs/terminal-verification.md)：终端与宿主验证范围。
- [ROADMAP.md](ROADMAP.md)：当前进度、未完成事项和验证记录。

## 看不到数据时

1. 先运行 `tokenbar status --providers auto --json --no-color`；实验性 provider 直接指定名称，检查该项 `source`、`error`、`stale` 和 `tokens`。
2. Claude Code 检查 `~/.claude/projects/` 是否有新的 JSONL 会话。
3. Kimi Code 检查 `~/.kimi-code/sessions/` 是否有 `wire.jsonl`；旧版目录是 `~/.kimi/`。
4. 如果使用自定义目录，按 [环境变量](#环境变量) 设置目录；`source` 指向的文件还需要包含对应 reader 能识别的字段。
5. 有 token 但没有 `ctx` 或 `5h`／`7d` 时，检查来源是否提供上下文容量或额度窗口；这类进度不会根据 token 数量推算。

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
- **手动运行 `tokenbar kimi-statusline` 没有数据**：这是 stdin 回调，应由 Kimi 调用，或使用上面的模拟 JSON 管道；在交互终端中单独执行会立即返回。查询本地会话使用 `tokenbar status --providers kimi`。
- **独立终端能运行，宿主状态栏却不显示**：检查配置中的命令路径是否能在宿主环境找到；优先使用虚拟环境中可执行文件的绝对路径，再重载或重启宿主。
- **缓存显示过期**：检查 JSON 中的 `stale` 和 `updated_at`；重新触发真实宿主回调刷新缓存。缓存过期不会自动生成新的 token 或额度数据。
- **Kimi 显示“未找到可识别 token 字段”**：检查 `wire.jsonl` 是否包含 `usage`。Kimi Code 原生 `usage.record` 的 `inputOther`、`output`、`inputCacheRead` 和 `inputCacheCreation` 已支持；如果日志字段完全不同，请提供字段名而不要发送会话正文。

## 许可证

[MIT License](LICENSE)
