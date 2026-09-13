# ROADMAP

## 当前状态

- 进行中：三 CLI 集成。Claude Code、Kimi Code 的原生 status-line stdin 适配器已实现；Codex 使用原生 `tui.status_line` 加 Stop Hook／旁路 watch。
- 待确认：Kimi Code 本机未安装，无法完成真实 TUI 重载验证；日志扫描适配器仍需要真实会话 fixture。
- 待确认：Claude Code 的账户级限额在当前本地日志中没有稳定字段；原生 statusLine 若由 Claude 传入 `rate_limits` 则可直接显示。

## 最近完成

- 2026-09-14 交付：创建 `ai-cli-statusline` 独立项目骨架、只读适配器、统一渲染器和离线测试。
- 2026-09-14 00:15 交付：增加 `integrate claude|kimi|codex` 配置说明、Claude/Kimi stdin 状态栏命令和 5 项离线测试；测试通过。

## 后续

1. 用真实 Claude Code 新会话补充 token 字段 fixture，并验证 watch 增量。
2. 在安装 Kimi Code 的环境中执行 `/reload-tui`，验证底部栏实时刷新和额度字段。
3. 增加 tmux/终端标题输出，但不把外部重绘误称为 Codex 原生底部状态栏。
4. 增加发布前的隐私审计、安装说明和版本化 changelog。
