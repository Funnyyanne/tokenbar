# Provider 支持审计

更新日期：2026-09-28

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
| OpenCode | stable | 新版 `session.tokens_*`；旧版在 SQLite 内用 `json_extract` 聚合 assistant `message.data.tokens` | Python 不接收消息正文；数据库只读且仅返回 usage/model 路径 | 合成新旧 schema 均有回归；本机旧 schema 读取成功，5 个会话汇总可用 |
| Cursor | experimental／受限 | 专用受限 adapter，不打开本地数据库 | 已知方案需从 Cursor SQLite 读取 auth token 再调用远端用量接口；本项目明确拒绝 | 回归测试证明 adapter 不调用 SQLite；当前只返回隐私限制原因，不提供用量 |
| Gemini CLI | experimental | `~/.gemini/tmp/<project>/chats/session-*.json` 的 Gemini message `tokens` | 只聚合 `type=gemini` 的 token/model，不输出正文 | 官方保存格式证据 + 正反 fixture；本机有旧会话但没有 token 字段，不宣称实机成功 |
| Pi、OMP | experimental | `~/.pi/agent/sessions`／`~/.omp/agent/sessions` 的 assistant message `usage` | 只处理 `type=message`、`role=assistant`；忽略 `usage.cost` 和正文 | 官方／上游会话格式 + 正反 fixture；本机未安装或无会话 |
| Goose | experimental | `sessions.db.usage_ledger` 的明确 token/model 列 | SQLite 只读，不读取 messages | 官方 schema + 合成 fixture；本机未安装 |
| Roo | experimental | Roo 专属 globalStorage 或 `~/.roo` 下的 `history_item.json` | 只读 `tokensIn`、`tokensOut`、`cacheReads`、`cacheWrites`、model；不扫描其他扩展目录 | 官方类型定义 + 合成 fixture；本机未安装 |
| GitHub Copilot CLI | experimental | `COPILOT_OTEL_FILE_EXPORTER_PATH` 或 `~/.copilot/otel/*.jsonl` 的 OTel `chat` span | 默认要求关闭 content capture；忽略 root span，按 span ID 去重，避免双计 | 官方 OTel 文档 + plain／typed attribute fixture；本机安装但尚未启用 OTel |
| Kilo | experimental | Kilo SQLite `session.tokens_*` | 正向白名单只读 session 聚合列 | 官方 schema／migration + 正反 fixture；本机未安装 |
| Zed | experimental／受限 | `threads.db` 中 `data_type=json` 的旧线程 `request_token_usage` | 不读取正文用于输出；现代 zstd payload 暂不解压 | 官方源码 + JSON fixture；现代格式明确返回限制，本机未安装 |
| AnythingLLM | experimental | `workspace_chats.response` 内的 `$.metrics` | 使用 SQLite `json_extract`，完整 response 不返回 Python | 官方 DB schema + fixture；本机未安装 |
| Devin | experimental | `sessions.db.message_nodes.chat_message.$.metadata.metrics` | 使用 SQLite `json_extract`，完整 chat message 不返回 Python | 公开独立实现交叉证据 + fixture；缺少官方稳定 schema，本机未安装 |
| ZCode | experimental | `~/.zcode/cli/db/db.sqlite.model_usage` | 只读明确 token/model 列；使用 provider/computed total 避免 cache/reasoning 双计 | 官方 schema／写入逻辑 + fixture；本机未安装 |
| Antigravity、DeepSeek、OmO、Craft、Reasonix | planned | 没有确认公开、稳定的本地 token schema | 不再使用目录 + 通用 JSONL 猜测 | 显式指定返回 unavailable 原因 |
| LM Studio | planned | 官方 API 响应有 usage，但未确认安全、持久的本地 token 日志 | 不代理用户 API、不读取 model IO 日志 | 显式指定返回 unavailable；可行方向是未来增加显式代理／hook Goal |
| Qoder | planned | 官方 `/usage` 是 credits 视图，未确认本地 token 字段 | 不读取认证信息，不把 credits 当 token | 显式指定返回 unavailable |
| MiMo | planned | 官方只确认本地 SQLite 目录，未公开可核对的 token 表结构 | 不把 OpenCode 相似性当作 schema 证据 | 显式指定返回 unavailable |

## 关键实现依据

- OpenCode 官方当前 `session` 表提供独立的 token 汇总列，因此无需读取包含消息内容的 `message.data`：[OpenCode session schema](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/session/sql.ts) 、[session usage migration](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/database/migration/20260510033149_session_usage.ts) 。
- Kimi Code 官方保存 `wire.jsonl`，SDK 明确给出 `inputOther`、`inputCacheRead`、`inputCacheCreation` 和 output 语义：[Kimi sessions](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/guides/sessions.md) 、[usage guide](https://github.com/MoonshotAI/kimi-agent-sdk/blob/main/guides/go/costs-and-usage.md) 。
- Gemini CLI 官方保存会话包含 token 统计，其 `TokensSummary` 定义了 input、output、cached、thoughts 和 total：[session management](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md) 、[chat recording types](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/services/chatRecordingTypes.ts) 。
- Goose、Roo、Kilo、ZCode 均有可核对的官方 schema：[Goose usage ledger](https://github.com/aaif-goose/goose/blob/main/crates/goose/src/session/session_manager.rs) 、[Roo history type](https://github.com/RooCodeInc/Roo-Code/blob/main/packages/types/src/history.ts) 、[Kilo session schema](https://github.com/Kilo-Org/kilocode/blob/main/packages/core/src/session/sql.ts) 、[ZCode usage repository](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/adapters/src/storage/session-store/repositories/usage.ts) 。
- Copilot CLI 官方 OTel file exporter提供 `chat` span token 字段，并明确 root／child 可能重复 AIU；本项目仅累计 chat token span：[Copilot CLI monitoring](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#opentelemetry-monitoring) 。
- LM Studio 官方 API 响应提供 usage，但 model/server log 主要面向模型输入输出与调试，不能据此假设存在安全持久的 token 日志：[REST API](https://lmstudio.ai/docs/developer/rest/endpoints) 、[log stream](https://lmstudio.ai/docs/cli/log-stream) 。
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
