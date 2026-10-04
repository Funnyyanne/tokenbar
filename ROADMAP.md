# ROADMAP

## 当前状态

- 未完成：TokenTracker 终端 CLI 全覆盖 Goal。已核对固定版本 956e3ab3，登记 44 个 provider，23 个新增／由 planned 升级的专用 reader 通过离线回归；38 个 reader 有明确用量格式，Kiro 仅覆盖旧 CLI 会话，当前只有 3 个返回本机 token。Goal 工具当前返回 usageLimited，未标记完整目标完成。施工清单保存在本机忽略目录 `goals/20261003-1900-terminal-cli-coverage.md`；可随代码获取的映射与缺口见 [工具覆盖表](docs/terminal-cli-coverage.md) 。
- 已完成：可信多 CLI 用量接入 Goal 已消除 SQLite 凭据误读、伪 token、缓存／长会话错误和不实 provider 支持声明；验收与支持矩阵见 [Provider 支持审计](docs/provider-support-audit.md) 。
- stable：Codex、Claude Code、Kimi Code、OpenCode；`--providers auto` 只包含这些有专用 reader／协议与回归证据的 provider。
- experimental：现有及新增专用 reader 必须显式启用或使用 `--providers all`；来源与限制统一见 [覆盖表](docs/terminal-cli-coverage.md) 。WorkBuddy 支持主／子会话树与明确 trace 回退，OMP／OmO 汇总嵌套子代理；Copilot 原生表优先，Devin request_id 全局去重，ZCode 合并新旧历史并排除镜像；Grok／DeepSeek Harness／LM Studio／Antigravity 有专用 reader，Kiro 仅读旧 CLI 明确计数，新增项仍仅离线验证。Zed 仅支持未压缩旧线程。
- 受限／planned：Cursor 仍只返回受限原因；官方 SDK 独立存储有明确用量，CLI 是否共用尚未确认，不用 SDK 证据代替 CLI 验收。Craft、Kilo Code、Unsloth、TRAE、TRAE Work CN 仍无专用 reader。新版 Kiro CLI 的安全来源继续核对；字符估算和 credits 不符合 tokenbar 的 token 边界。
- 待确认：本机已安装 Kimi Code 2.0.0，但当前没有可识别会话，真实 TUI 重载未验证；真实 Claude／Kimi 额度仍依赖官方状态栏快照或本地会话字段。
- 待确认：当前沙箱中 Codex 本地 token 读取正常，但 app-server 额度 RPC 提前退出；不将离线回归冒充实时额度验证。
- 已完成：44-provider 本机全集合核查；仅 Codex、Claude、OpenCode 当前返回 token，均无真实额度窗口。既有 Kimi 原生上下文协议、watch 刷新／窄屏／信号清理的 PTY 回归继续通过；原生宿主与跨系统效果仍待验证，历史证据见 [终端验证报告](docs/terminal-verification.md) 。
- 已完成：`tokenbar integrate codex` 只读说明命令的 TypeError 已修复，移除无对应实现的 Stop Hook 引用；模拟命令回归确认退出码 0 且不创建配置目录，中文 README 已恢复该命令示例。

## 最近完成

- 2026-10-04 12:11 交付：基于远端 main 的 fb8c7ca 独立检出整合已授权的 CLI reader、计数回退、会话树与 README 改动，保留 main 上 Zed 全历史扫描和专用 reader 自定义目录修复；恢复 integrate codex 只读说明命令并补回归。PR 范围为这些检查点，完整 CLI Goal 仍未完成。
- 2026-10-04 01:35 交付：完善中文 README 的导航、跨平台源码安装、默认 provider／auto 区别、命令参数与 JSON 字段、宿主可执行文件路径、环境变量、通用 JSONL 读取边界、开发入口及排错；核对 Claude／Kimi／Copilot 官方配置说明，移除当前报错的 integrate codex 示例。本轮只修改 README 与本进度文档。
- 2026-10-04 01:20 交付：补齐 WorkBuddy 主／子会话树、同会话明细优先和两种 trace 明确总量回退；补齐 OMP／OmO 嵌套子代理汇总与同 ID 修正替换，保留各自 reasoning 语义和其他 provider 单文件统计。同步双语 README、审计、覆盖表与施工清单；Cursor 官方 SDK 用量与 CLI 存储关联尚待确认，完整 Goal 未完成。
- 2026-10-03 20:23 交付：修复 ZCode 原生 completed 记录遗漏明确 provider／computed 总量、NULL／0 父计数时遗漏 cache／reasoning 的回退；完整父计数不重复相加。修复 Grok 混合有效／无效模型明细的少计，回退到有效顶层 usage，并保留修正替换与全零明细回退。同步双语 README、支持审计和覆盖表；只处理本次两条审查问题。
- 2026-10-03 19:51 交付：新增 Antigravity 原生 generation metadata reader，只计已完成 planner，读取活动 WAL，拒绝字符／上下文估算；新增 Kiro 旧 CLI 会话明确计数 reader，保留 loop 0、去重和修正替换，新版 chars／credits 不计 token。同步双语 README、审计、覆盖表与施工清单；当前为 4 stable／35 experimental／5 planned，完整 Goal 仍未完成。
- 2026-10-03 19:34 交付：接入 Grok turn_completed／modelUsage、DeepSeek Harness v0／v3 多帧 zstd、LM Studio 最终响应日志；补齐 Copilot 原生表与 OTel 两种缓存语义、Devin 分叉／重放去重、ZCode 新旧 schema 与镜像过滤。新增 project dependency zstandard 并记录发布／维护核查；同步双语 README、审计和覆盖表。完整 CLI Goal 仍进行中。
- 2026-10-03 19:13 交付：增加 CodeBuddy、WorkBuddy、OmO、Dots、Prime、MiniMax、Command Code、Reasonix、MiMo、OpenClaw、Droid、Hermes、Claude Science、Cline、AStudio、Every Code、Qoder／Qoder CN 共 18 个专用 reader；JSON 改用标量投影，修复 Pi／OMP 长日志与去重、Kilo 旧 schema fallback、SQLite 初始化失败时连接关闭；提供 `--providers all` 与专用 parser 的自定义目录，更新双语 README 和 [覆盖表](docs/terminal-cli-coverage.md) 。本条只代表该检查点，完整 CLI Goal 仍进行中。
- 2026-10-03 11:16 交付：完善双语 README 的 Python 版本检查、Kimi stdin 示例、连续 JSON 和退出码说明；将上下文进度、终端清理和 provider 校验修复整合到 main 基线 bbf41c4，保留既有 provider 回归修复。
- 2026-10-03 00:21 交付：修复 watch 收到 SIGTERM 后遗留备用屏幕／隐藏光标，以及无效 provider 错误被屏幕恢复隐藏的问题；退出时恢复先前信号处理器，进入屏幕前完整校验 provider，更新双语 README 和终端验证报告。
- 2026-10-02 17:32 交付：更新双语 README 的 24-provider 能力表、auto 入门命令和进度语义；移除没有对应实现的 Stop Hook 使用说明；基于最新远端 main 准备独立 PR 改动，保留既有 Zed／自定义目录修复。
- 2026-10-02 17:20 交付：核对 24 个 provider 和固定版本 TokenTracker；修复 Kimi camelCase 上下文回调、Claude 缓存占用回退、非有限百分比崩溃、stdin 渲染选项和 watch 无颜色刷新；增加分行／窄屏与额度重置倒计时，交付 [验证报告](docs/terminal-verification.md) 。
- 2026-09-29 08:41 交付：复核并收紧 OpenCode、ZCode、Zed、AnythingLLM／Devin SQLite reader 的只读连接生命周期，连接初始化失败时安全跳过；未改变 provider 字段白名单与隐私边界。
- 2026-09-28 23:21 交付：重新核实 Claude／Codex 之外的 provider；新增 Gemini、Pi／OMP、Copilot OTel 专用 reader，修复 OpenCode 旧 schema 实机不可读、AnythingLLM／Devin 正文列读取和 ZCode cache／reasoning 双计；证据不足的 8 个 provider 降级为 planned／受限。
- 2026-09-23 22:30 交付：为 Goose、Roo、LM Studio、Copilot、Kilo、Zed、Qoder、AnythingLLM、Devin、MiMo、ZCode 接入实验性专用 reader；Qoder 仅接受明确 usage 对象，避免将 credits 或认证信息冒充 token；新增合成 SQLite／JSON fixture 与失败隔离回归测试。

- 2026-09-23 21:28 交付：修复长 JSONL 全量读取、Codex 空 token 数据库回退和无数据状态错误成功码；46 项测试通过。
- 2026-09-19 09:07 交付：完成可信多 CLI 用量接入 Goal；SQLite 改为正向字段白名单，修复 Codex 部分失败／多库回退、缓存合并／TTL／并发写、8 MiB JSONL 尾部读取限制和 CLI 失败隔离；新增 OpenCode 专用 reader、Cursor 隐私受限 adapter、provider 成熟度注册和支持审计。
- 2026-09-18 00:21 交付：修复 Kimi `[status_line]` 表头尾随注释导致重复表的问题，写回前验证 TOML；JSONL 扫描不再因 50 个较新无用量文件遗漏有效会话。
- 2026-09-17 23:58 交付：应用 Kimi 配置修复 patch，补强 Codex 状态数据库选择、文件扫描竞态、SQLite 汇总和缓存测试隔离；23 项测试通过。
- 2026-09-17 23:10 交付：修复已有 `[status_line]` 段缺少 `command` 时的 TOML 插入位置，避免 `setup kimi --force` 生成无效配置；17 项测试通过。
- 2026-09-17 22:55 交付：接入 Kimi Code `usage.record` 的 `inputOther`、`output`、`inputCacheRead` 和 `inputCacheCreation` 字段；15 项测试通过。

## 最近验证

- 2026-10-04 12:13：独立 Python 3.11 venv 中按源码安装入口执行 editable install 成功；tokenbar --version、integrate codex 和 pip check 通过。最终六份文档的链接／锚点／围栏与 Bash、JSON、TOML 示例检查通过，44 项 registry 映射完整，暂存范围与 diff 检查通过。
- 2026-10-04 12:11：最终 PR 检出全量 pytest 324 项通过（含 main 既有回归与新增 Codex 说明命令回归），compileall 通过；44-provider JSON 冒烟仍仅 Codex／Claude／OpenCode 返回 token，41 项无 token、全部无额度窗口；integrate codex 成功且不写配置。新增 reader 仍仅离线格式验证，未生成付费会话或改写外部 CLI 配置。
- 2026-10-04 01:35：中文 README 的 44 项 provider 映射、目录锚点／相对链接、代码围栏、20 个 Bash 代码块语法及 JSON／TOML 示例解析通过；在任务目录隔离回调缓存，help／version、integrate claude／kimi、两种模拟 stdin 回调与自定义 JSONL 120-token 示例通过。复现 integrate codex 的 TypeError 并登记待修复；未执行 Windows 安装、真实宿主或付费会话，不改外部 CLI 配置。
- 2026-10-04 01:23：双语 README、ROADMAP、支持审计、覆盖表和本机施工清单的相对链接／代码围栏检查通过；44 项 registry 在双语能力表与覆盖表均有映射；最近完成 20 条、最近验证未超过 20 条。JSON 的 rate_limits 字段已核对，44 项合计 0 个额度窗口。
- 2026-10-04 01:20：全量 pytest 315 项通过（本检查点新增 44 项）；先复现 WorkBuddy／OMP／OmO 单文件漏计，再验证主／子去重、修正／零值、孤立子树、两种 trace envelope、错误计数、外部 lineage 拒读、来源字节不变与专用 roots。compileall、git diff --check 通过；44-provider JSON 冒烟无 ANSI／traceback，仍仅 Codex／Claude／OpenCode 有 token、41 项无 token、全部无额度窗口。kiro-cli --version 返回 2.2.2，未创建计费会话；新增适配仅离线验证，未提交或推送。
- 2026-10-03 20:23：新增离线回归先复现两处计数遗漏，修复后全量 pytest 271 项通过；新增 23 项覆盖 ZCode 明确总量优先级、缺失父计数、缓存／reasoning 不重复计数、凭据列拒读和数据库字节不变，以及 Grok 混合无效明细、全零明细、无有效顶层计数与同 ID 修正替换。compileall、git diff --check、受影响文档链接／围栏检查通过；未验证真实 CLI 会话，未提交、推送或修改外部配置。
- 2026-10-03 19:51：当前工作区全量 pytest 248 项通过；新增两项 fixture 覆盖 protobuf 截断／溢出、缓存／reasoning、上下文-only、活动 WAL、SQLite 私有表拒读、Kiro loop／message ID 去重和错误计数。compileall、git diff --check、文档链接／围栏及 44 项 registry 映射检查通过；44-provider JSON 冒烟仍仅 Codex／Claude／OpenCode 返回 token，41 项无 token、全部无额度窗口。新增 reader 缺实机日志；未提交或修改外部 CLI 配置。
- 2026-10-03 19:34：当前工作区全量 pytest 227 项通过；新增 fixture 覆盖三项 reader、原生 Copilot／Devin／ZCode、跨帧／截断／迁移／镜像／修正，SQLite authorizer 证实不查询凭据／费用明细列。compileall、git diff --check、文档链接／围栏及 44 项 registry 映射检查通过；44-provider JSON 冒烟仅 Codex／Claude／OpenCode 返回 token，41 项无 token、全部无额度窗口。新增接入仍缺实机日志，未修改外部 CLI 配置或提交／发布。
- 2026-10-03 19:13：当前工作区 171 项 pytest 通过（包含原有 POSIX PTY 用例）；compileall、git diff --check、文档相对链接／围栏与 44 项 registry 文档映射检查通过。44-provider JSON 冒烟只有 Codex、Claude、OpenCode 返回 token，41 项无 token、全部无额度窗口；新增 reader 仅有离线专用格式证据，无真实宿主／会话证明。
- 2026-10-03 11:16：在独立 PR 检出、main 基线 bbf41c4 上运行全量 pytest（122 项通过）、compileall、git diff --check；24-provider JSON 冒烟、README Kimi 示例、相对链接及代码围栏检查通过。仅 Codex／Claude／OpenCode 本地 token 可读，实时额度仍未取得。
- 2026-10-03 00:21：新增回归修复前复现 4 个 SIGTERM 场景和 2 个共享 stdout／stderr TTY 的无效 provider 场景；修复后当前工作区全量 114 项 pytest、compileall、git diff --check 通过。10 项 PTY 用例覆盖 SIGINT／SIGTERM、无颜色／NO_COLOR／JSON／dumb 及原屏幕错误；另验证信号处理器恢复与无效列表不查询有效前缀。
- 2026-10-02 17:32：README 相对链接、代码围栏及 git diff --check 通过；原工作区 105 项 pytest 通过；临时最新 main 检出应用本轮完整改动后 113 项 pytest、compileall、24-provider JSON 冒烟通过。远端基线为 bbf41c4，该检查仅代表当时的独立检出状态。
- 2026-10-02 17:20：105 项 pytest、compileall、`git diff --check` 通过；24-provider JSON／文本冒烟无 traceback；4 个 PTY 用例确认 25% → 75% 更新、NO_COLOR／--no-color 重绘、JSON／dumb 无控制码和 SIGINT 屏幕恢复；真实三平台 watch 及 OpenCode 无颜色终端刷新通过；Kimi 脱敏回调本机 5 次调用 121.1～149.8 ms，真实宿主 TUI 未验证。
- 2026-09-29 08:42：新增 provider registry 覆盖回归用例；重新运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`（61 项通过）、`compileall` 和 `git diff --check`；22 provider JSON 冒烟无 traceback，实机仍仅 OpenCode 旧 schema 返回 token 汇总。
- 2026-09-28 23:21：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，60 项测试全部通过；本机 OpenCode 旧 schema 的 5 个会话成功读取 token 汇总；其他未安装／无会话平台只完成官方格式和脱敏 fixture 验证。
- 2026-09-23 22:30：运行 `PYTHONPATH=src pytest -q`，51 项测试全部通过；实验性 reader 使用合成 SQLite／JSON fixture 验证，未读取真实账号数据。

- 2026-09-22 20:07：在 `dev` 分支运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，45 项测试全部通过；`compileall` 与 `git diff --check` 通过，准备以 `main` 为基准提交 PR。
- 2026-09-19 09:07：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，45 项测试全部通过；`compileall` 与 `git diff --check` 通过。
- 2026-09-19 09:06：运行五 provider 与 `auto` 的 JSON 状态命令，均无 traceback；Codex 本地 token 与 Claude 实机日志可读，Kimi／OpenCode 无本机会话，Cursor 按隐私限制返回 unavailable。
- 2026-09-18 00:21：运行 `PYTHONPATH=src /usr/local/bin/python3.11 -m pytest -q`，26 项测试全部通过。

## 后续

1. 继续 TokenTracker CLI 全覆盖 Goal：核对新版 Kiro CLI 与安全的 Cursor CLI token 来源，确认 Cursor SDK 与 CLI 的存储关系。旧 Kiro 和 Antigravity 明确元数据 reader 已实现但仍缺实机证据，不采用字符／credits 估算。完整边界见覆盖表，不缩小为已有 reader 的完成状态；Goal 工具仍为 usageLimited，当前按用户继续指令推进检查点，自动执行需恢复 Goal 状态。
2. 补齐各 CLI subagent、跨版本与真实会话证据，执行 Kimi `/reload-tui`；未证明前保留 experimental／unavailable。
3. 为 JSONL 增加可安全失效的增量索引，降低长会话在 `watch` 中重复完整扫描的成本。
4. 增加成本引擎、daily／weekly／monthly 报表和 `doctor`／`diagnostics`／`unsetup` 生命周期。
