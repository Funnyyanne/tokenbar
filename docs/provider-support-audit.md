# Provider 支持审计

更新日期：2026-10-04

本文件记录 tokenbar 实际拥有的 reader、数据源、隐私边界和验证证据。“发现常见目录”不等于“支持 provider”；只有数据格式明确、reader 专用且有脱敏回归测试时，才标为 stable。

## 成熟度定义

- `stable`：有专用 reader 或正式 stdin 协议、明确数据源、脱敏 fixture 和通过的回归测试；进入 `--providers auto`。
- `experimental`：有专用或通用 reader，但尚缺充分实机／跨版本证据，或能力受限；必须显式指定，不进入 `auto`。
- `planned`：已知可能的数据源，但没有满足隐私与准确性要求的 reader；显式指定时只返回 unavailable 和原因。

## 当前矩阵

当前登记 44 个 provider：4 个 stable、35 个 experimental（其中 Cursor 不返回用量）、5 个 planned。38 个 reader 能识别明确的用量格式；这不等于 38 项实机可用或当前版本完整支持，Kiro 仅支持旧 CLI 会话。44 项本机核查仍仅 Codex、Claude、OpenCode 返回 token，全部未返回账户额度窗口。完整工具映射、23 个新增／升级 reader 的离线证据与未完成范围见 [工具覆盖表](terminal-cli-coverage.md) 。旧版 24-provider 实测记录保留在 [终端验证报告](terminal-verification.md) 。

| Provider | 成熟度 | 数据源与 reader | 隐私边界 | 验证证据与限制 |
| --- | --- | --- | --- | --- |
| Codex | stable | `codex app-server --stdio` 只读额度 RPC；`state_*.sqlite` 的 `threads.tokens_used` | SQLite 只读；不读认证文件或消息正文 | 合成数据库覆盖多库回退、空库回退和额度部分失败；本机 app-server 受沙箱限制，实时额度未验证 |
| Claude Code | stable | `~/.claude/projects/**/*.jsonl`；官方 `statusLine` stdin | 只解析 usage、model、context 和 rate-limit 元数据 | 脱敏 JSONL 与 stdin fixture；长文件完整统计、缓存合并和过期回归通过 |
| Kimi Code | stable | `~/.kimi-code/**/wire.jsonl`；官方 stdin 的 `contextTokens`／`maxContextTokens` | 只解析 usage／context 元数据；配置写回前完整 TOML 验证 | 脱敏 `usage.record`、TOML 和官方 camelCase stdin fixture；本机无可识别会话，真实 `/reload-tui` 未验证 |
| OpenCode | stable | 新版 `session.tokens_*`；旧版在 SQLite 内用 `json_extract` 聚合 assistant `message.data.tokens` | Python 不接收消息正文；数据库只读且仅返回 usage/model 路径 | 合成新旧 schema 均有回归；本机旧 schema 读取成功，5 个会话汇总可用 |
| Cursor | experimental／受限 | 专用受限 adapter，不打开本地数据库 | 参考方案需读取 auth token 并调用远端接口；官方 SDK 有独立本地明确用量，但 CLI 是否共用尚未确认 | 回归证明 adapter 不调用 SQLite；当前不提供用量，SDK 发现不能代替 CLI 验收，详见覆盖表 |
| Gemini CLI | experimental | `~/.gemini/tmp/<project>/chats/session-*.json` 的 Gemini message `tokens` | 只聚合 `type=gemini` 的 token/model，不输出正文 | 官方保存格式证据 + 正反 fixture；本机有旧会话但没有 token 字段，不宣称实机成功 |
| Pi、OMP | experimental | `~/.pi/agent/sessions`／`~/.omp/agent/sessions` 的 assistant message `usage` | 标量投影，全文件流读、ID 去重；OMP 汇总主／子会话树，reasoningTokens 独立计；Pi 排除 Dots | 官方／上游格式 + 长会话／修正／嵌套子代理 fixture；本机未安装或无会话 |
| Goose | experimental | `sessions.db.usage_ledger` 的明确 token/model 列 | SQLite 只读，不读取 messages | 官方 schema + 合成 fixture；本机未安装 |
| Roo | experimental | Roo 专属 globalStorage 或 `~/.roo` 下的 `history_item.json` | 只读 `tokensIn`、`tokensOut`、`cacheReads`、`cacheWrites`、model；不扫描其他扩展目录 | 官方类型定义 + 合成 fixture；本机未安装 |
| GitHub Copilot CLI | experimental | 原生 `session-store.db.assistant_usage_events` 优先，OTel fallback | 只读 id／input／output／model；不读 token_details_json 或凭据；CLI 父计数含缓存／reasoning；不合并原生镜像 | 固定参考源码＋原生表、CLI／Chat OTel、长日志、修正／共享 context、空表与只读 fixture；缺实机会话 |
| Kilo CLI | experimental | Kilo SQLite `session.tokens_*` 或旧 `message.data.tokens` | 正向白名单，SQLite 内提取旧 schema 的 usage/model | 新旧 schema fixture；不等于 Kilo Code 扩展 reader，本机未安装 |
| Zed | experimental／受限 | `threads.db` 中 `data_type=json` 的旧线程 `request_token_usage` | 不读取正文用于输出；现代 zstd payload 暂不解压 | 官方源码 + JSON fixture；现代格式明确返回限制，本机未安装 |
| AnythingLLM | experimental | `workspace_chats.response` 内的 `$.metrics` | 使用 SQLite `json_extract`，完整 response 不返回 Python | 官方 DB schema + fixture；本机未安装 |
| Devin | experimental | `$XDG_DATA_HOME/devin/cli/sessions.db` 的 assistant request_id／metrics | SQLite 标量投影；全局去重分叉／重放，所属会话和修正排序；缓存列独立；不查询 cogs_json | 固定参考源码＋分叉、修正、未完成／无效指标、只读字段与路径 fixture；缺实机会话 |
| ZCode | experimental | `~/.zcode/cli/db/db.sqlite` 的 completed model_usage＋迁移前 message | SQLite 标量白名单；排除 bundled 镜像、保留自定义 UUID；原生记录优先有效非零 provider／computed 总量，NULL／0 父计数回退到 cache／reasoning，完整父计数不重复加子计数 | 新旧 schema、明确总量／缺失父计数、镜像／失败状态、迁移边界和凭据拒读／只读 fixture；缺实机会话 |
| WorkBuddy | experimental | projects JSONL 主／子会话树；traces/**/trace_*.json 明确总量回退 | 同 ID 修正替换；明细优先于同会话 trace；cache／reasoning 已含父计数；不读 context／credits 数据库 | 离线 fixture 覆盖两种 trace envelope、镜像、全零修正、只读与错误输入；缺本机会话 |
| OmO | experimental | `.omo/agent/sessions` 的主／子会话树 | assistant usage 标量投影、同 ID 修正替换；reasoning 已含 output；不跟随外部 lineage 路径 | 固定上游格式与嵌套／孤立子树、截断、错误计数 fixture；缺本机会话 |
| CodeBuddy、Dots、Prime、MiniMax、Command Code、Reasonix、OpenClaw、Droid、Cline、AStudio、Every Code、Hermes、Claude Science | experimental | 专用 JSON 元数据／SQLite 字段，入口和语义见 [覆盖表](terminal-cli-coverage.md) | JSON 标量投影，不解码正文对象；SQLite 白名单，只读；cache／reasoning 按来源分辨子集 | 离线 fixture 覆盖去重、边界、错误格式与失败路径；当前缺本机有效会话 |
| Antigravity | experimental | 三种 app 目录的 conversations/*.db.gen_metadata；对应 brain transcript 已完成 PLANNER_RESPONSE | 只读明确 protobuf 字段与完成标量；不查询 messages／auth 表，不采用字符／context 估算；读取活动 WAL | 固定参考源码＋缓存／reasoning、修正、截断／溢出、上下文-only、WAL 与 authorizer fixture；缺实机会话 |
| Kiro CLI | experimental／部分支持 | KIRO_HOME/sessions/cli/{UUID}.json 的明确 input_token_count／output_token_count | SQLite JSON 标量投影，loop／message ID 去重；不解码正文，不将 chars／credits 转为 token | 旧格式去重、修正、错误字段与私有正文 fixture；新版 messages.jsonl／数据库尚无已确认可靠 token 来源，仍属于 Goal 缺口 |
| Craft、Kilo Code、Unsloth、TRAE、TRAE Work CN | planned | 本项目尚无专用 reader；TRAE Work CN 的已知凭据路径超出边界 | 不使用目录 + 通用 JSONL 猜测，不读取凭据 | 显式指定返回 unavailable；GUI-only 来源不替代终端 CLI 验收 |
| Grok Build | experimental | updates.jsonl 的 turn_completed usage／modelUsage | 只投影明确元数据；完整有效模型明细优先，明细不完整时回退到有效顶层用量；整次事件修正替换；忽略上下文水位 | 混合有效／无效明细、重复／错误／正文 usage 和 camel／snake 缓存语义 fixture；缺实机会话 |
| DeepSeek Harness | experimental | session[.vN].jsonl[.zstd] 的明确 assistant usage | 有界多帧解压、不写正文；标量投影；seq 去重，截断帧不计 | v0／v3、跨帧、重复／修正、活动版本、错误帧／指标与上限 fixture；缺实机会话 |
| LM Studio | experimental | server-logs 的 Final response usage | 只投影顶层元数据；父计数含缓存／reasoning；轮转日志响应去重 | Chat／Responses、修正／镜像、超过 8 MiB 正文、混合文本／截断及错误计数 fixture；缺实机日志 |
| Qoder、Qoder CN | experimental | CLI projects JSONL 的 assistant message usage；GUI token_info DB 尚未接入 | 缓存列独立，忽略 credits，不读认证信息 | 正反 fixture；CN／国际版目录分离；缺实机日志 |
| MiMo | experimental | mimocode.db 的 OpenCode message usage 专用投影 | 只接受 mimo／xiaomi providerID，排除镜像；不使用混入镜像的 session 汇总 | 官方参考字段、正反与只读 fixture；缺本机有效会话 |

## 关键实现依据

- OpenCode 官方当前 `session` 表提供独立的 token 汇总列，因此无需读取包含消息内容的 `message.data`：[OpenCode session schema](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/session/sql.ts) 、[session usage migration](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/database/migration/20260510033149_session_usage.ts) 。
- Kimi Code 官方保存 `wire.jsonl`，SDK 明确给出 `inputOther`、`inputCacheRead`、`inputCacheCreation` 和 output 语义：[Kimi sessions](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/guides/sessions.md) 、[usage guide](https://github.com/MoonshotAI/kimi-agent-sdk/blob/main/guides/go/costs-and-usage.md) 。
- Gemini CLI 官方保存会话包含 token 统计，其 `TokensSummary` 定义了 input、output、cached、thoughts 和 total：[session management](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md) 、[chat recording types](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/services/chatRecordingTypes.ts) 。
- Goose、Roo、Kilo、ZCode 均有可核对的官方 schema：[Goose usage ledger](https://github.com/aaif-goose/goose/blob/main/crates/goose/src/session/session_manager.rs) 、[Roo history type](https://github.com/RooCodeInc/Roo-Code/blob/main/packages/types/src/history.ts) 、[Kilo session schema](https://github.com/Kilo-Org/kilocode/blob/main/packages/core/src/session/sql.ts) 、[ZCode usage repository](https://github.com/zai-org/ZCode/blob/main/apps/zcode-cli/packages/adapters/src/storage/session-store/repositories/usage.ts) 。
- Copilot CLI 官方 OTel file exporter提供 `chat` span token 字段，并明确 root／child 可能重复 AIU；本项目仅累计 chat token span：[Copilot CLI monitoring](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#opentelemetry-monitoring) 。
- Grok、DeepSeek Harness、LM Studio、Antigravity、Kiro 旧会话及 Copilot／Devin 原生格式按 [固定版本解析器](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/src/lib/rollout.js) 和对应上游专用测试核对；离线格式证据不等于本机真实会话或厂商稳定 schema 承诺。
- 参考项目 stormzhang/token-tracker 当前公开数据源集中在 Claude Code、Codex 和 Kimi Code，并强调只读：[数据来源](https://github.com/stormzhang/token-tracker/blob/main/README.md#数据来源) 。
- xiufengsun/TokenTracker 的 Cursor 方案需要本地 auth token 与远端 CSV 接口；这不符合本项目“不读取认证凭据”的边界，因此没有照搬：[支持工具说明](https://github.com/xiufengsun/TokenTracker/wiki/Supported-AI-Tools-zh-CN#cursor) 。
- 同一参考项目对不同工具分别使用 hook、插件、OTEL 或专用数据库 reader，说明不能用一个通用 SQLite 猜测器等价替代真实接入：[支持工具说明](https://github.com/xiufengsun/TokenTracker/wiki/Supported-AI-Tools-zh-CN) 。

## 接入新 Provider 的门槛

本轮新增 reader 的固定来源依据、依赖核查和剩余范围见 [工具覆盖表](terminal-cli-coverage.md) 。没有将新增 reader 升级为 stable，也没有将原生 fixture 视为当前实机 CLI 的完整覆盖。

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
| 中 | 更多状态栏字段与实机额度证据 | 重置倒计时已实现；成本、项目／分支和响应速度仍未接入，真实额度仍需上游数据，每个字段必须有明确来源 |
| 中 | 更多专用 provider 接入 | 参考项目使用 hook、插件、OTEL 和专用数据库等不同方式覆盖更多工具；应按 provider 分批实现，不能恢复通用猜测器 |
| 低／产品扩展 | 侧边栏、热力图、Web Dashboard、原生菜单栏／托盘、桌面组件、宠物、成就和 Skills 管理 | 两个参考项目已覆盖其中多项，但它们明显扩大产品与隐私边界，应作为独立产品 Goal，而不是混入状态栏核心 |

参考依据：stormzhang/token-tracker 提供 sidebar、额度倒计时、成本与 daily／weekly／monthly／sessions 报表、setup／unsetup 等能力；xiufengsun/TokenTracker 提供本地 Dashboard、多工具 hook／插件接入、原生桌面与组件等更大产品面。详见 [stormzhang/token-tracker README](https://github.com/stormzhang/token-tracker/blob/main/README_EN.md) 和 [xiufengsun/TokenTracker README](https://github.com/xiufengsun/TokenTracker/blob/main/README.md) 。
