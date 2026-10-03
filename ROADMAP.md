# ROADMAP

## 当前状态

- 已完成：可信多 CLI 用量接入 Goal 已消除 SQLite 凭据误读、伪 token、缓存／长会话错误和不实 provider 支持声明；验收与支持矩阵见 [Provider 支持审计](docs/provider-support-audit.md) 。
- stable：Codex、Claude Code、Kimi Code、OpenCode；`--providers auto` 只包含这些有专用 reader／协议与回归证据的 provider。
- experimental：Gemini、Pi、OMP、Goose、Roo、Copilot、Kilo、Zed、AnythingLLM、Devin、ZCode 有 provider-specific reader，必须显式启用；Zed 仅支持未压缩旧线程，Copilot 需要先启用官方 OTel 文件导出。
- 受限／planned：Cursor 因凭据边界只返回受限原因；Antigravity、DeepSeek、OmO、Craft、Reasonix、LM Studio、Qoder、MiMo 尚无本项目经验证的专用 reader。参考项目已有对应方向，不再把本项目缺口表述成外部没有来源。
- 待确认：本机已安装 Kimi Code 2.0.0，但当前没有可识别会话，真实 TUI 重载未验证；真实 Claude／Kimi 额度仍依赖官方状态栏快照或本地会话字段。
- 待确认：当前沙箱中 Codex 本地 token 读取正常，但 app-server 额度 RPC 提前退出；不将离线回归冒充实时额度验证。
- 已完成：24-provider 本机核查与终端进度修复；仅 Codex、Claude、OpenCode 当前返回 token，均无真实额度／上下文百分比。Kimi 原生上下文协议已修复，watch 无颜色刷新、窄屏、SIGINT／SIGTERM 清理及无效 provider 在原屏幕报错经 PTY 验证；完整边界见 [终端与平台验证报告](docs/terminal-verification.md) 。

## 最近完成

- 2026-10-03 11:16 交付：完善双语 README 的 Python 版本检查、Kimi stdin 示例、连续 JSON 和退出码说明；将上下文进度、终端清理和 provider 校验修复整合到 main 基线 bbf41c4，保留既有 provider 回归修复。
- 2026-10-03 00:21 交付：修复 watch 收到 SIGTERM 后遗留备用屏幕／隐藏光标，以及无效 provider 错误被屏幕恢复隐藏的问题；退出时恢复先前信号处理器，进入屏幕前完整校验 provider，更新双语 README 和终端验证报告。
- 2026-10-02 17:32 交付：更新双语 README 的 24-provider 能力表、auto 入门命令和进度语义；移除没有对应实现的 Stop Hook 使用说明；基于最新远端 main 准备独立 PR 改动，保留既有 Zed／自定义目录修复。
- 2026-10-02 17:20 交付：核对 24 个 provider 和固定版本 TokenTracker；修复 Kimi camelCase 上下文回调、Claude 缓存占用回退、非有限百分比崩溃、stdin 渲染选项和 watch 无颜色刷新；增加分行／窄屏与额度重置倒计时，交付 [验证报告](docs/terminal-verification.md) 。
- 2026-10-01 17:44 交付：修复 Zed 仅扫描最新 20 条线程导致漏计／错误 unavailable 的回归，逐行统计所有可识别 JSON 线程；恢复 Gemini、Pi、OMP 专用 reader 对 `AI_CLI_STATUSLINE_SOURCES` 的目录优先配置，并同步双语使用说明。
- 2026-09-29 08:41 交付：复核并收紧 OpenCode、ZCode、Zed、AnythingLLM／Devin SQLite reader 的只读连接生命周期，连接初始化失败时安全跳过；未改变 provider 字段白名单与隐私边界。
- 2026-09-28 23:21 交付：重新核实 Claude／Codex 之外的 provider；新增 Gemini、Pi／OMP、Copilot OTel 专用 reader，修复 OpenCode 旧 schema 实机不可读、AnythingLLM／Devin 正文列读取和 ZCode cache／reasoning 双计；证据不足的 8 个 provider 降级为 planned／受限。
- 2026-09-23 22:30 交付：为 Goose、Roo、LM Studio、Copilot、Kilo、Zed、Qoder、AnythingLLM、Devin、MiMo、ZCode 接入实验性专用 reader；Qoder 仅接受明确 usage 对象，避免将 credits 或认证信息冒充 token；新增合成 SQLite／JSON fixture 与失败隔离回归测试。

- 2026-09-23 21:28 交付：修复长 JSONL 全量读取、Codex 空 token 数据库回退和无数据状态错误成功码；46 项测试通过。
- 2026-09-19 09:07 交付：完成可信多 CLI 用量接入 Goal；SQLite 改为正向字段白名单，修复 Codex 部分失败／多库回退、缓存合并／TTL／并发写、8 MiB JSONL 尾部读取限制和 CLI 失败隔离；新增 OpenCode 专用 reader、Cursor 隐私受限 adapter、provider 成熟度注册和支持审计。
- 2026-09-18 00:21 交付：修复 Kimi `[status_line]` 表头尾随注释导致重复表的问题，写回前验证 TOML；JSONL 扫描不再因 50 个较新无用量文件遗漏有效会话。
- 2026-09-17 23:58 交付：应用 Kimi 配置修复 patch，补强 Codex 状态数据库选择、文件扫描竞态、SQLite 汇总和缓存测试隔离；23 项测试通过。
- 2026-09-17 23:10 交付：修复已有 `[status_line]` 段缺少 `command` 时的 TOML 插入位置，避免 `setup kimi --force` 生成无效配置；17 项测试通过。
- 2026-09-17 22:55 交付：接入 Kimi Code `usage.record` 的 `inputOther`、`output`、`inputCacheRead` 和 `inputCacheCreation` 字段；15 项测试通过。
- 2026-09-17 01:07 交付：重构 Claude/Kimi JSONL 解析、增加状态栏缓存和 `setup` 配置命令，扩展 JSONL／SQLite provider、主题和纯文本进度样式；14 项测试通过。
- 2026-09-14 00:15 交付：增加 `integrate claude|kimi|codex` 配置说明、Claude/Kimi stdin 状态栏命令和 5 项离线测试；测试通过。
- 2026-09-14 交付：创建 `tokenbar` 独立项目骨架、只读适配器、统一渲染器和离线测试。

## 最近验证

- 2026-10-03 11:16：在独立 PR 检出、main 基线 bbf41c4 上运行全量 pytest（122 项通过）、compileall、git diff --check；24-provider JSON 冒烟、README Kimi 示例、相对链接及代码围栏检查通过。仅 Codex／Claude／OpenCode 本地 token 可读，实时额度仍未取得。
- 2026-10-03 00:21：新增回归修复前复现 4 个 SIGTERM 场景和 2 个共享 stdout／stderr TTY 的无效 provider 场景；修复后当前工作区全量 114 项 pytest、compileall、git diff --check 通过。10 项 PTY 用例覆盖 SIGINT／SIGTERM、无颜色／NO_COLOR／JSON／dumb 及原屏幕错误；另验证信号处理器恢复与无效列表不查询有效前缀。
- 2026-10-02 17:32：README 相对链接、代码围栏及 git diff --check 通过；原工作区 105 项 pytest 通过；临时最新 main 检出应用本轮完整改动后 113 项 pytest、compileall、24-provider JSON 冒烟通过。远端基线为 bbf41c4，该检查仅代表当时的独立检出状态。
- 2026-10-02 17:20：105 项 pytest、compileall、`git diff --check` 通过；24-provider JSON／文本冒烟无 traceback；4 个 PTY 用例确认 25% → 75% 更新、NO_COLOR／--no-color 重绘、JSON／dumb 无控制码和 SIGINT 屏幕恢复；真实三平台 watch 及 OpenCode 无颜色终端刷新通过；Kimi 脱敏回调本机 5 次调用 121.1～149.8 ms，真实宿主 TUI 未验证。
- 2026-10-01 17:44：新增 8 项合成 fixture 回归场景，覆盖超过 20 条有效 Zed 线程、较新压缩／无用量线程、自定义目录有数据／为空；修复前均失败，修复后全量 69 项测试通过。此次仅完成离线回归，未验证真实 provider 会话。
- 2026-09-29 08:42：新增 provider registry 覆盖回归用例；重新运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`（61 项通过）、`compileall` 和 `git diff --check`；22 provider JSON 冒烟无 traceback，实机仍仅 OpenCode 旧 schema 返回 token 汇总。
- 2026-09-28 23:21：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，60 项测试全部通过；本机 OpenCode 旧 schema 的 5 个会话成功读取 token 汇总；其他未安装／无会话平台只完成官方格式和脱敏 fixture 验证。
- 2026-09-23 22:30：运行 `PYTHONPATH=src pytest -q`，51 项测试全部通过；实验性 reader 使用合成 SQLite／JSON fixture 验证，未读取真实账号数据。

- 2026-09-22 20:07：在 `dev` 分支运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，45 项测试全部通过；`compileall` 与 `git diff --check` 通过，准备以 `main` 为基准提交 PR。
- 2026-09-19 09:07：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，45 项测试全部通过；`compileall` 与 `git diff --check` 通过。
- 2026-09-19 09:06：运行五 provider 与 `auto` 的 JSON 状态命令，均无 traceback；Codex 本地 token 与 Claude 实机日志可读，Kimi／OpenCode 无本机会话，Cursor 按隐私限制返回 unavailable。
- 2026-09-18 00:21：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，26 项测试全部通过。

## 后续

1. 为 JSONL 增加可安全失效的增量索引，降低长会话在 `watch` 中重复完整扫描的成本。
2. 用真实 Kimi Code／OpenCode 会话补充跨版本 fixture，并执行 Kimi `/reload-tui` 验证。
3. 用真实 Goose、Roo、Copilot OTel、Kilo、Zed、AnythingLLM、Devin、ZCode 会话补齐跨版本实机证据，再评估是否升级 stable。
4. 增加成本引擎、daily／weekly／monthly 报表和 `doctor`／`diagnostics`／`unsetup` 生命周期。
