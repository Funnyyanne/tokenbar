# ROADMAP

## 当前状态

- 进行中：多 CLI 统一采集。Claude Code、Kimi Code 已支持多文件回退、官方状态栏 stdin 缓存和新版会话路径；Codex 使用 app-server／SQLite 与 Stop Hook。
- 待确认：Kimi Code 本机未安装，无法完成真实 TUI 重载验证；真实 Claude／Kimi 额度仍依赖官方状态栏快照或本地会话字段。
- 已支持：Gemini、Pi、OMP、OmO、Goose 等 JSONL 工具；Cursor、OpenCode、Copilot、Kilo、Zed、Qoder、AnythingLLM、Devin、Mimo、ZCode 等 SQLite 工具；并可通过 `AI_CLI_STATUSLINE_SOURCES` 添加自定义 CLI 日志目录。

## 最近完成

- 2026-09-14 交付：创建 `tokenbar` 独立项目骨架、只读适配器、统一渲染器和离线测试。
- 2026-09-14 00:15 交付：增加 `integrate claude|kimi|codex` 配置说明、Claude/Kimi stdin 状态栏命令和 5 项离线测试；测试通过。
- 2026-09-17 01:07 交付：重构 Claude/Kimi JSONL 解析、增加状态栏缓存和 `setup` 配置命令，扩展 JSONL／SQLite provider、主题和纯文本进度样式；14 项测试通过。
- 2026-09-17 22:55 交付：接入 Kimi Code `usage.record` 的 `inputOther`、`output`、`inputCacheRead` 和 `inputCacheCreation` 字段；15 项测试通过。
- 2026-09-17 23:10 交付：修复已有 `[status_line]` 段缺少 `command` 时的 TOML 插入位置，避免 `setup kimi --force` 生成无效配置；17 项测试通过。

## 后续

1. 用真实 Claude Code 新会话和 Kimi Code `wire.jsonl` 补充跨版本 fixture，并验证 watch 增量。
2. 在安装 Kimi Code 的环境中执行 `/reload-tui`，验证底部栏实时刷新和额度字段。
3. 为 OpenTelemetry 类型的其他 CLI 增加独立 reader，避免通用 JSONL／SQLite parser 误读。
4. 增加发布前的隐私审计、安装说明和版本化 changelog。
