# ROADMAP

## 当前状态

- 已完成：可信多 CLI 用量接入 Goal 已消除 SQLite 凭据误读、伪 token、缓存／长会话错误和不实 provider 支持声明；验收与支持矩阵见 [Provider 支持审计](docs/provider-support-audit.md) 。
- stable：Codex、Claude Code、Kimi Code、OpenCode；`--providers auto` 只包含这些有专用 reader／协议与回归证据的 provider。
- experimental：Cursor 因认证凭据边界只返回受限原因；Gemini、Antigravity、DeepSeek、Pi、OMP、OmO、Craft、Reasonix 仅提供通用 JSONL 解析，必须显式启用。
- planned：Goose、Roo、LM Studio、Copilot、Kilo、Zed、Qoder、AnythingLLM、Devin、Mimo、ZCode 等等待专用 reader，不再使用通用 SQLite 猜测。
- 待确认：本机已安装 Kimi Code 2.0.0，但当前没有可识别会话且未配置 `status_line`，无法完成真实 TUI 重载验证；真实 Claude／Kimi 额度仍依赖官方状态栏快照或本地会话字段。
- 待确认：当前沙箱中 Codex 本地 token 读取正常，但 app-server 额度 RPC 提前退出；不将离线回归冒充实时额度验证。

## 最近完成

- 2026-09-19 09:07 交付：完成可信多 CLI 用量接入 Goal；SQLite 改为正向字段白名单，修复 Codex 部分失败／多库回退、缓存合并／TTL／并发写、超过 8 MiB 的完整 JSONL 统计和 CLI 失败隔离；新增 OpenCode 专用 reader、Cursor 隐私受限 adapter、provider 成熟度注册和支持审计。
- 2026-09-18 00:21 交付：修复 Kimi `[status_line]` 表头尾随注释导致重复表的问题，写回前验证 TOML；JSONL 扫描不再因 50 个较新无用量文件遗漏有效会话。
- 2026-09-17 23:58 交付：应用 Kimi 配置修复 patch，补强 Codex 状态数据库选择、文件扫描竞态、SQLite 汇总和缓存测试隔离；23 项测试通过。
- 2026-09-17 23:10 交付：修复已有 `[status_line]` 段缺少 `command` 时的 TOML 插入位置，避免 `setup kimi --force` 生成无效配置；17 项测试通过。
- 2026-09-17 22:55 交付：接入 Kimi Code `usage.record` 的 `inputOther`、`output`、`inputCacheRead` 和 `inputCacheCreation` 字段；15 项测试通过。
- 2026-09-17 01:07 交付：重构 Claude/Kimi JSONL 解析、增加状态栏缓存和 `setup` 配置命令，扩展 JSONL／SQLite provider、主题和纯文本进度样式；14 项测试通过。
- 2026-09-14 00:15 交付：增加 `integrate claude|kimi|codex` 配置说明、Claude/Kimi stdin 状态栏命令和 5 项离线测试；测试通过。
- 2026-09-14 交付：创建 `tokenbar` 独立项目骨架、只读适配器、统一渲染器和离线测试。

## 最近验证

- 2026-09-22 20:07：在 `dev` 分支运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，45 项测试全部通过；`compileall` 与 `git diff --check` 通过，准备以 `main` 为基准提交 PR。
- 2026-09-19 09:07：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，45 项测试全部通过；`compileall` 与 `git diff --check` 通过。
- 2026-09-19 09:06：运行五 provider 与 `auto` 的 JSON 状态命令，均无 traceback；Codex 本地 token 与 Claude 实机日志可读，Kimi／OpenCode 无本机会话，Cursor 按隐私限制返回 unavailable。
- 2026-09-18 00:21：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，26 项测试全部通过。

## 后续

1. 为 JSONL 增加可安全失效的增量索引，降低长会话在 `watch` 中重复完整扫描的成本。
2. 用真实 Kimi Code／OpenCode 会话补充跨版本 fixture，并执行 Kimi `/reload-tui` 验证。
3. 分 Goal 为 Gemini 系、Copilot OTEL、Goose、Kilo／Mimo／ZCode 等增加专用 reader。
4. 增加成本引擎、daily／weekly／monthly 报表和 `doctor`／`diagnostics`／`unsetup` 生命周期。
