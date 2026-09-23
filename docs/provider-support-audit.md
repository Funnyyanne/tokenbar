# Provider 支持审计

更新日期：2026-09-19

本文件记录 tokenbar 实际拥有的 reader、数据源、隐私边界和验证证据。“发现常见目录”不等于“支持 provider”；只有数据格式明确、reader 专用且有脱敏回归测试时，才标为 stable。

## 成熟度定义

- `stable`：有专用 reader 或正式 stdin 协议、明确数据源、脱敏 fixture 和通过的回归测试；进入 `--providers auto`。
- `experimental`：仅有受限能力或通用 JSONL 解析；必须显式指定，不进入 `auto`。
- `planned`：已知可能的数据源，但没有满足隐私与准确性要求的 reader；显式指定时只返回 unavailable 和原因。

## 当前矩阵

| Provider | 成熟度 | 数据源与 reader | 隐私边界 | 验证证据与限制 |
| --- | --- | --- | --- | --- |
| Codex | stable | `codex app-server --stdio` 只读额度 RPC；`state_*.sqlite` 的 `threads.tokens_used` | SQLite 只读；不读认证文件或消息正文 | 合成数据库覆盖多库回退、空库回退和额度部分失败；本机 app-server 受沙箱限制，实时额度未验证 |
| Claude Code | stable | `~/.claude/projects/**/*.jsonl`；官方 `statusLine` stdin | 只解析 usage、model、context 和 rate-limit 元数据 | 脱敏 JSONL 与 stdin fixture；长文件完整统计、缓存合并和过期回归通过 |
| Kimi Code | stable | `~/.kimi-code/**/wire.jsonl`；官方 `[status_line].command` stdin | 只解析 usage 元数据；配置写回前完整 TOML 验证 | 脱敏 `usage.record`、TOML 和 stdin fixture；本机 Kimi Code 2.0.0 无可识别会话，真实 `/reload-tui` 未验证 |
| OpenCode | stable | `opencode.db`／`db.sqlite` 的 `session.tokens_input`、`tokens_output`、`tokens_reasoning`、`tokens_cache_read`、`tokens_cache_write` | 正向白名单只查询 `session` 用量列；不查询 `message.data`、`event.data` 或认证字段 | 合成 SQLite 覆盖正常、错误 schema、较新无效库回退和消息／事件重复数据隔离；未做本机真实会话验证 |
| Cursor | experimental／受限 | 专用受限 adapter，不打开本地数据库 | 已知方案需从 Cursor SQLite 读取 auth token 再调用远端用量接口；本项目明确拒绝 | 回归测试证明 adapter 不调用 SQLite；当前只返回隐私限制原因，不提供用量 |
| Gemini、Antigravity、DeepSeek、Pi、OMP、OmO、Craft、Reasonix | experimental | 常见目录上的通用 JSONL reader | 仅解析通用 usage 字段，不读取正文用于输出 | 有通用解析器测试，但没有逐 provider 官方 schema fixture；必须显式指定 |
| Goose、Roo、LM Studio、Copilot、Kilo、Zed、Qoder、AnythingLLM、Devin、Mimo、ZCode | planned | 已登记候选本地来源，无可用 reader | 不进行通用 SQLite 猜测，不查询任何未知 token 列 | 显式指定时返回需要专用 reader 的原因；不进入 `auto` |

## 关键实现依据

- OpenCode 官方当前 `session` 表提供独立的 token 汇总列，因此无需读取包含消息内容的 `message.data`：[OpenCode session schema](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/session/sql.ts) 、[session usage migration](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/database/migration/20260510033149_session_usage.ts) 。
- 参考项目 stormzhang/token-tracker 当前公开数据源集中在 Claude Code、Codex 和 Kimi Code，并强调只读：[数据来源](https://github.com/stormzhang/token-tracker/blob/main/README.md#数据来源) 。
- xiufengsun/TokenTracker 的 Cursor 方案需要本地 auth token 与远端 CSV 接口；这不符合本项目“不读取认证凭据”的边界，因此没有照搬：[支持工具说明](https://github.com/xiufengsun/TokenTracker/wiki/Supported-AI-Tools-zh-CN#cursor) 。
- 同一参考项目对不同工具分别使用 hook、插件、OTEL 或专用数据库 reader，说明不能用一个通用 SQLite 猜测器等价替代真实接入：[支持工具说明](https://github.com/xiufengsun/TokenTracker/wiki/Supported-AI-Tools-zh-CN) 。

## 接入新 Provider 的门槛

新增 stable provider 必须同时具备：

1. 官方格式或可运行参考实现能够确认字段语义。
2. 正向白名单 reader，只访问明确的用量元数据。
3. 脱敏 fixture 覆盖正常、空数据、错误 schema、重复／旋转数据和失败路径。
4. 文档明确说明来源、成熟度、隐私边界、离线验证与实机验证状态。
5. `--providers auto` 下单个 provider 失败不会阻断其他 provider，也不会输出 traceback。

## 与参考项目相比仍缺少的功能

以下是审查后的真实差距，不属于本 Goal 已完成范围：

| 优先级 | 功能差距 | 价值与建议 |
| --- | --- | --- |
| 高 | 增量日志索引与断点续读 | 当前为保证准确性会完整扫描 JSONL；长生命周期会话在 `watch` 中仍有性能成本。应按文件标识、大小和偏移保存可失效的增量聚合，并覆盖截断、轮转和重写 |
| 高 | 成本与定价引擎 | 尚无逐模型价格、缓存读写价格、长上下文阶梯或缺价警告；不能仅用 token 猜成本。建议独立 Goal 建立版本化价格来源和可复现计算 |
| 高 | 历史报表和 session 明细 | 尚无 daily／weekly／monthly、项目／模型趋势、会话时长和消息数；需要先定义本地历史存储、去重与迁移边界 |
| 高 | `doctor`／`diagnostics`／`unsetup` | 当前错误信息已有改善，但缺少可分享的脱敏诊断、接入状态检查，以及精确恢复 Claude／Kimi 配置的卸载生命周期 |
| 中 | 额度重置倒计时与更完整状态栏字段 | 当前仅展示部分百分比；可增加 reset countdown、成本、项目／分支和响应速度，但每个字段必须有明确来源 |
| 中 | 更多专用 provider 接入 | 参考项目使用 hook、插件、OTEL 和专用数据库等不同方式覆盖更多工具；应按 provider 分批实现，不能恢复通用猜测器 |
| 低／产品扩展 | 侧边栏、热力图、Web Dashboard、原生菜单栏／托盘、桌面组件、宠物、成就和 Skills 管理 | 两个参考项目已覆盖其中多项，但它们明显扩大产品与隐私边界，应作为独立产品 Goal，而不是混入状态栏核心 |

参考依据：stormzhang/token-tracker 提供 sidebar、额度倒计时、成本与 daily／weekly／monthly／sessions 报表、setup／unsetup 等能力；xiufengsun/TokenTracker 提供本地 Dashboard、多工具 hook／插件接入、原生桌面与组件等更大产品面。详见 [stormzhang/token-tracker README](https://github.com/stormzhang/token-tracker/blob/main/README_EN.md) 和 [xiufengsun/TokenTracker README](https://github.com/xiufengsun/TokenTracker/blob/main/README.md) 。
