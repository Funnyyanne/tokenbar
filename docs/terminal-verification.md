# 终端与平台验证报告

验证时间：2026-10-02 17:20（北京时间）。

目前登记的 24 个 provider 并非全部可用。本轮本机可读 token 的只有 Codex、Claude Code 和 OpenCode；24 项均未返回真实上下文百分比或账户额度窗口。已有 reader 的离线适配能力与本机当前数据可用性必须分开判断。

## 逐平台结果

本机只读验证通过各 provider 的现有 reader；不新增登录、不读取凭据、不修改 CLI 配置、不生成付费会话。没有 CLI／日志不会伪造成功。下表“可读”可能来自已有历史会话，不能证明这些应用当前正在产生新用量。

| Provider | 成熟度 | 本轮本机结果 | 终端进度与使用边界 |
| --- | --- | --- | --- |
| Codex | stable | 本地 token 可读；CLI 0.159.3 | 额度 RPC 提前退出，保留 token 并显示额度错误；无真实额度／上下文进度 |
| Claude Code | stable | 本地 token 可读；CLI 2.1.133 | 当前日志无上下文／额度；stdin 的进度及缓存输入统计经脱敏 fixture 验证 |
| Kimi Code | stable | CLI 2.0.0；无可识别 token | 已修复官方 flat stdin 上下文协议，回调模拟验证通过；真实 `/reload-tui` 未验证 |
| OpenCode | stable | 本地 SQLite token 可读；CLI 1.4.6 | 当前来源没有可靠上下文／额度分母，仅展示 token |
| Gemini CLI | experimental | CLI 0.49.0；保存会话无可识别 token | 已有专用 reader 和格式 fixture，缺少本机有效用量记录 |
| Pi | experimental | PATH 无 CLI；无 assistant usage | 专用会话 fixture 通过，本机使用未验证 |
| OMP | experimental | PATH 无 CLI；无 assistant usage | 专用会话 fixture 通过，本机使用未验证 |
| Goose | experimental | 无可读 token | usage ledger fixture 通过，本机使用未验证 |
| Roo | experimental | 无可读 token | history item fixture 通过，本机使用未验证 |
| Copilot | experimental | PATH 无 CLI；无可读 OTel chat span | 需要已有官方 OTel 导出；未自动修改配置，fixture 通过 |
| Kilo | experimental | 无可读 token | session schema fixture 通过，本机使用未验证 |
| Zed | experimental | 无可读 token | 仅旧 JSON 线程格式有 fixture；现代压缩线程受限 |
| AnythingLLM | experimental | 无可读 token | SQLite 内只提取 metrics 的 fixture 通过，本机使用未验证 |
| Devin | experimental | 无可读 token | metrics fixture 通过，缺少官方稳定 schema 及本机证据 |
| ZCode | experimental | 无可读 token | model usage fixture 通过，本机使用未验证 |
| Cursor | experimental／受限 | 按隐私边界返回 unavailable | 已知参考额度路径需凭据及远端请求，本项目不采用该路径 |
| Antigravity | planned | 尚未实现经验证的 reader | 只返回明确 unavailable，不显示进度 |
| DeepSeek Harness | planned | 尚未实现经验证的 reader | 只返回明确 unavailable，不显示进度 |
| OmO | planned | 尚未实现经验证的 reader | 只返回明确 unavailable，不显示进度 |
| Craft | planned | 尚未实现经验证的 reader | 只返回明确 unavailable，不显示进度 |
| Reasonix | planned | 尚未实现经验证的 reader | 只返回明确 unavailable，不显示进度 |
| LM Studio | planned | 尚未实现经验证的 reader | 只返回明确 unavailable，不显示进度 |
| Qoder | planned | 尚未实现经验证的 reader | credits 不能冒充 token／上下文占用 |
| MiMo | planned | 尚未实现经验证的 reader | 只返回明确 unavailable，不按类似数据库猜测 |

有 token 不等于有进度：上下文需要实际占用量与容量；额度需要上游已用百分比。错误状态与部分成功数据可以同时显示。planned 平台代表 tokenbar 的实现缺口，不能概括成外部平台没有可行方案。

## 参考实现与协议核对

- TokenTracker 参考版本：`24614b13d37c0f602808fbd88f0aabba743c96a0`。[usage-limits.js](https://github.com/xiufengsun/TokenTracker/blob/24614b13d37c0f602808fbd88f0aabba743c96a0/src/lib/usage-limits.js) 中 `clampPercent`／`buildWindow` 明确拒绝非有限百分比并保存重置时间；[status.js](https://github.com/xiufengsun/TokenTracker/blob/24614b13d37c0f602808fbd88f0aabba743c96a0/src/commands/status.js) 提供无 spinner 的轻量文本和 JSON 路径。本轮采用相应显示原则，保持 tokenbar 现有只读边界。
- 参考项目已列出本项目 8 个 planned 平台的被动读取方向，包括 Qoder `token_info`、LM Studio final-response usage、MiMo SQLite；这说明本项目缺少 reader，不能继续断言外部没有来源。[固定版本支持工具表](https://github.com/xiufengsun/TokenTracker/tree/24614b13d37c0f602808fbd88f0aabba743c96a0#supported-ai-tools) 。本轮未将这些描述直接升级为 tokenbar 支持声明。
- Kimi 官方核对版本：`21406fb4c805cc8c715e6d1f16ad3fb5f25f4fe3`。[StatusLinePayload](https://github.com/MoonshotAI/kimi-code/blob/21406fb4c805cc8c715e6d1f16ad3fb5f25f4fe3/apps/kimi-code/src/tui/utils/status-line-command.ts) 明确提供 `contextTokens`／`maxContextTokens`，回调限制 300 ms；原适配器按 Claude 对象格式读取，导致进度缺失，现已修复。不会将上下文占用当作累计 token。
- Claude 官方说明：上下文百分比由 input、cache creation、cache read 三项计算，不包含 output。本轮修复缺少官方百分比时的回退计算及缓存输入计数。[Claude Code status line](https://code.claude.com/docs/en/statusline#context-window-fields) 。

## 终端显示行为

- `watch` 按平台分行，按 Unicode 显示宽度折行；`status` 和 stdin 回调保持一行。
- 可控制 TTY 中使用独立屏幕，`--no-color`／`NO_COLOR` 下仍刷新，Ctrl-C 或 SIGTERM 退出时恢复屏幕与光标。
- JSON、重定向或 `TERM=dumb` 不发送屏幕控制码；watch 采用追加输出。
- 进度统一显示已用比例；NaN／Infinity 显示未知，不导致回调崩溃。来源没有分母时不显示虚假进度。
- 上游提供重置时间时显示 `reset in`；到期显示 `reset due`，等待新快照，保留当前已用比例。
- 日志 model／error 等文本中的控制字符不会变成终端控制序列或新行。

可从源码直接运行，本机未发现 PATH 中的 `tokenbar` 可执行命令：

```bash
PYTHONPATH=src /usr/local/bin/python3.11 -m ai_cli_statusline watch --providers codex,claude,opencode --interval 5
```

下列为脱敏模拟回调输出，不代表真实 Kimi 账户或真实 TUI 截图：

```text
Kimi · kimi-k2 · ctx .......... 0% used
Kimi · kimi-k2 · ctx ##........ 25% used
Kimi · kimi-k2 · ctx #####..... 50% used
Kimi · kimi-k2 · ctx ########.. 75% used
Kimi · kimi-k2 · ctx ########## 100% used
```

## 验证证据

1. 原 HEAD 下 6 个回归用例失败，复现 Kimi 进度丢失、Claude 缓存占用遗漏、NaN／Infinity 崩溃和 stdin 选项不生效；修复后全部通过。
2. `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`：105 项通过。包含 4 个真实 POSIX PTY 子进程用例：实际追加模拟日志、观察 25% → 75% 两帧进度、无颜色重绘、JSON／dumb 输出及 SIGINT 退出恢复。
3. 40 列 PTY 和带中文的 32 列渲染回归覆盖窄屏；没有声称完成所有终端模拟器／字体／操作系统的视觉验收。
4. 24-provider `status --json --no-color` 返回 24 项，集合与 registry 完全一致；文本包含全部平台标签，无控制码、stderr 或 traceback；聚合命令退出码为 0，因为有 3 个平台返回数据。另运行真实 Codex／Claude／OpenCode 的多帧 watch，观察到 token 更新；在 `TERM=xterm-256color` 的 TTY 中运行 OpenCode `watch --no-color`，确认多次重绘与 Ctrl-C 后屏幕／光标恢复，所有验证进程均已退出。
5. Kimi 脱敏 stdin 的 0%、25%、50%、75%、100% 进度均以一行输出；本机 5 次独立进程耗时 121.1～149.8 ms，低于官方 300 ms 上限。这只是本机回调调用证据，不等于 Kimi 宿主 TUI 验证。
6. `compileall` 与 `git diff --check` 通过。未读写认证配置，未提交或推送；临时脱敏汇总在 `.tmp/terminal-provider-audit/verification.json`，正式使用不依赖该文件。

尚未证明的范围：Codex 实时账户额度、Kimi `/reload-tui`、其他平台的真实有效会话、真实 host-TUI 调用以及跨系统终端视觉效果。没有对应数据的平台保持 unavailable／planned；不会用模拟进度声称实机可用。

## 审查修复验证

2026-10-03 00:21（北京时间）：当前工作区新增回归测试，在修改实现前复现 SIGTERM 不执行终端清理，以及无效 provider 的诊断被备用屏幕恢复隐藏。修复后全量 114 项 pytest、compileall、`git diff --check` 通过。

- SIGTERM 转为退出码 143，经过与 Ctrl-C 相同的屏幕／光标清理路径；退出后恢复先前的 SIGTERM 处理器。Ctrl-C 保持退出码 0。
- 完整 provider 列表在切换屏幕前校验，不请求用量快照；无效名称以退出码 2 在原屏幕报错，不查询有效前缀平台。
- 10 项真实 PTY 子进程用例覆盖 SIGINT／SIGTERM，在无颜色、NO_COLOR、JSON 和 dumb 输出下的退出行为，以及 stdout／stderr 共享同一终端时单个／混合无效名称的可见诊断。
- 本次审查验证针对当时的工作区；后续 PR 基线整合验证见下文。

## PR 基线整合验证

2026-10-03 11:16（北京时间）：将本轮完整改动应用到远端 main 的 `bbf41c4` 基线，保留既有 Zed 与自定义目录修复。独立 PR 检出中 122 项 pytest、compileall、`git diff --check` 全部通过；24-provider JSON 冒烟与 README 的 Kimi 模拟示例、相对链接、代码围栏检查通过。该结果更新了前述临时 PR 检出尚未同步的状态。真实账户额度和宿主 TUI 的验证边界不变。
