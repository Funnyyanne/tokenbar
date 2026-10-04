# TokenTracker 工具与终端 CLI 覆盖

核对日期：2026-10-04。上游固定版本：`956e3ab331ce265021ed61c73622a516e882da2e`。依据为 [上游 AI Tools 清单](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/README.md#-supported-ai-tools) 、[实际扫描入口](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/src/commands/sync.js) 和 [专用解析实现](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/src/lib/rollout.js) 。

完整目标仍未完成：支持清单中所有可在终端使用的 CLI。当前 44 个登记项包含 38 个能读取明确用量格式的 reader、1 个隐私受限项和 5 个 planned 项；Kiro reader 仅覆盖旧 CLI 会话。登记项数量与上游工具数量不是一对一关系，例如 Copilot 多种来源共用一个 provider，Qoder CN 单独登记。`all` 是全量核查入口，不能据此宣称全部工具已支持。

## 当前映射

`stable` 与 `experimental` 表示 reader 能力；后者仍缺实机／跨版本证据。下表的“fixture”仅指专用格式离线验证。无对应文件或字段时一律 unavailable。

| 上游工具 | tokenbar provider | 当前数据来源／边界 |
| --- | --- | --- |
| Claude Code | `claude`，stable | 既有会话日志与原生 stdin |
| Codex CLI | `codex`，stable | 既有 SQLite 与只读 app-server |
| AStudio | `astudio`，experimental | `.acode/{sessions,archived_sessions}` 的 rollout 累计快照；fixture |
| Cursor | `cursor`，受限 | 参考路径需要凭据；官方 SDK 有独立明确用量，尚未证明 CLI 共用其存储；没有安全的 Cursor CLI token reader |
| Kiro／Kiro CLI | `kiro`，experimental／部分支持 | KIRO_HOME/sessions/cli/{UUID}.json 的明确 input_token_count／output_token_count；loop／message ID 去重与修正替换；新版 JSONL 与请求数据库未确认可靠 token 字段，不采用 chars／credits；fixture |
| Gemini CLI | `gemini`，experimental | 既有保存会话 tokens |
| OpenCode | `opencode`，stable | 既有新旧 SQLite schema |
| OpenClaw | `openclaw`，experimental | `.openclaw/agents/*/sessions/*.jsonl`；input 已含 cacheRead，cacheWrite 单独计；fixture |
| Every Code | `everycode`，experimental | `.code/sessions` 的 rollout 累计快照；fixture |
| Hermes Agent | `hermes`，experimental | `.hermes/state.db.sessions`；独立 cache／reasoning 列；fixture |
| GitHub Copilot App／CLI／Chat extension | `copilot`，experimental | `session-store.db.assistant_usage_events` 优先，空原生表不恢复旧 OTel；OTel 区分 CLI span 与 Chat LogRecord 的缓存写入，按 trace／span 或 response ID 去重；不合并镜像；fixture |
| Kimi Code | `kimi`，stable | 既有 wire.jsonl 与原生 stdin；宿主 TUI 待验证 |
| oh-my-pi | `omp`，experimental | assistant usage，全文件扫描；汇总最新主／子会话树，同 ID 修正替换；reasoningTokens 独立计；fixture |
| CodeBuddy | `codebuddy`，experimental | `.codebuddy/projects/**/*.jsonl` 中的 providerData.rawUsage；支持 function_call／message 响应 ID 去重；fixture；不扫描 IDE 扩展日志 |
| WorkBuddy | `workbuddy`，experimental | `.workbuddy/projects` 主／subagents 会话树 rawUsage；同 ID 修正替换；缺明细时回退 `.workbuddy/traces/**/trace_*.json` 的明确总量，明细／trace 不叠加；SQLite context／credits 不计 token；fixture |
| Grok Build | `grok`，experimental | `.grok/sessions/**/updates.jsonl` 的 turn_completed usage；完整有效的 modelUsage 优先，混合无效明细时回退到有效顶层 usage；整次修正替换；camelCase input 含缓存，snake_case input 不含；不采用 context watermark；fixture |
| Kilo CLI | `kilo`，experimental | 新 session 汇总及旧 message usage；补齐旧 schema fallback；fixture |
| Kilo Code 扩展 | `kilocode`，planned | GUI／扩展来源，不能用 Kilo CLI 的 SQLite 冒充支持 |
| Antigravity | `antigravity`，experimental | `.gemini/{antigravity,antigravity-ide,antigravity-cli}/conversations/*.db` 的 gen_metadata；只计对应 brain transcript 已完成 planner 的明确 token；system／prompt／cache、text／reasoning 去重；活动 WAL；不采用字符／context 估算；fixture |
| OmO | `omo`，experimental | `.omo/agent/sessions` 主／嵌套子会话树；同 ID 修正替换，reasoning 是 output 子集，不额外计入；fixture |
| Pi | `pi`，experimental | assistant usage；Dots 后端分出，避免与 dots 重复显示；fixture |
| Dots | `dots`，experimental | 同一 Pi 来源，只选择标准化后 provider=dots 的记录；fixture |
| Prime Agent | `prime`，experimental | `.prime/agent/sessions/*.jsonl`；独立来源与去重；fixture |
| Craft Agents | `craft`，planned | 上游描述为桌面应用；workspace session header reader 未实现 |
| Reasonix | `reasonix`，experimental | 只读 `.jsonl.telemetry.json` 与 `.jsonl.meta`；不打开会话正文；累计 input／output 已含缓存／reasoning；fixture |
| Roo Code 扩展 | `roo`，experimental | 既有 history_item reader；当前上游 ui_messages 来源尚未接入 |
| Zed Agent | `zed`，experimental | 既有未压缩旧线程 reader；现代 zstd 受限 |
| Goose | `goose`，experimental | 既有 usage_ledger |
| Droid | `droid`，experimental | `.factory/sessions/**/*.settings.json` 的累计 tokenUsage；不累计两次轮询；fixture |
| Mimo Code | `mimo`，experimental | mimocode.db assistant tokens；只接受 providerID=mimo／xiaomi，兼容 model.providerID；不读包含镜像的 session 汇总；fixture |
| ZCode | `zcode`，experimental | `model_usage` 只计 completed；合并第一条原生记录之前的旧 message 历史；保留自定义 UUID provider，排除 anthropic／openai／google 镜像；原生记录优先有效非零 provider_total_tokens／computed_total_tokens，input／output 父计数为 NULL／0 时才回退到明确 cache／reasoning；不重复加到完整父计数；fixture |
| Qoder | `qoder`，experimental | `.qoder/projects/**/*.jsonl` 的 assistant usage；缓存列独立计；credits 不计 token；GUI token_info DB 尚未覆盖；fixture |
| Qoder CN（上游版本分支） | `qodercn`，experimental | 独立 `.qoder-cn/projects`；不读取账号额度；fixture |
| LM Studio | `lmstudio`，experimental | `.lmstudio/server-logs/**/*.log` 的完整 Final response usage；合并轮转日志、响应 ID 去重／修正替换；只投影顶层元数据，忽略正文内 usage；fixture；单条响应最多 128 MiB |
| Unsloth Studio | `unsloth`，planned | 上游 Studio metadata reader 尚未实现；仅通过命令启动 Web UI 不等于已有终端用量接入 |
| AnythingLLM Desktop | `anythingllm`，experimental | 既有 SQLite metrics；GUI 来源 |
| Devin CLI | `devin`，experimental | `$XDG_DATA_HOME/devin/cli/sessions.db`；仅已完成 assistant metrics；全局 request_id 去重，优先最早所属会话及其中最新修正；计入独立 cache_read／cache_creation；fixture |
| Cline CLI v3／桌面应用 | `cline`，experimental | `.cline/data/sessions/*/*.messages.json`；array／messages envelope、ID 去重、importedAt 前历史排除；input／output 已含缓存／reasoning；fixture；不读 VS Code 扩展格式 |
| MiniMax Code | `minimax`，experimental | `.minimax/v2/sessions/**/messages.jsonl`；message_id 去重，忽略 always-zero cost；fixture |
| Command Code | `commandcode`，experimental | `.commandcode/projects/**/*.jsonl`；跳过 checkpoints／prompts sidecar；input 已含缓存；ID 修正替换；fixture |
| Claude Science | `claudescience`，experimental | operon-cli.db／operon.db frames 主／aux 标量列；排除 token 为 NULL 的示例正文，兼容部分 cache 列；fixture |
| DeepSeek Harness | `deepseek`，experimental | `.dsh/sessions/**/session[.vN].jsonl[.zstd]`；v0／v3 明确 usage，seq 去重，input／cache／reasoning 各列独立；多帧解压，截断／错误帧 unavailable；同目录优先正在写入的版本；fixture |
| TRAE | `trae`，planned | GUI 本地 SQLCipher 元数据尚未实现 |
| TRAE Work CN | `traecn`，planned／受限 | 上游方案发送本地授权到内部 API，违反本项目不读取凭据的边界 |

## 终端使用

```bash
tokenbar status --providers all --json --no-color
tokenbar watch --providers codebuddy,workbuddy,omo,prime,minimax,commandcode,cline --interval 5
```

`auto` 仍只包含 Codex、Claude、Kimi、OpenCode。其他可用 reader 必须显式选择或使用 all。会话 reader 返回最新有效文件／数据库的统计；WorkBuddy／OMP／OmO 汇总同一逻辑会话树，LM Studio 合并所有轮转日志并去重。来源不同的 totals 不保证同一统计时间跨度；不得把 all 的数值直接当作全账户账单总和。

自定义目录使用 `AI_CLI_STATUSLINE_SOURCES`，例如 `{"minimax":["/absolute/path/to/sessions"],"hermes":["/absolute/path/to/data"]}`。已登记 reader 保留专用字段与过滤，不切换通用猜测。Cursor 的限制不会因此绕过。Codex／Cursor 不通过这个入口重定位；Codex 使用 CODEX_HOME。

新版 JSON reader 使用 Python 自带 SQLite JSON 函数投影固定的标量路径，Python 不对完整 prompt／reply 对象执行 json.loads；正文和认证字段不会返回 reader。JSONL 从头逐行读取，每次重建 snapshot，避免 8 MiB 尾读丢失与多次 watch 轮询叠加；长会话增量索引仍待实现。单个 JSON／Cline array 会整体读入原始文本，但仅白名单标量返回 Python，不缓存原始文本。

23 个新增／由 planned 升级的专用 reader 均保持 experimental。没有用量格式、字段不匹配或只有 credits 时返回 unavailable；不从 token 总数推算上下文／账户进度，不增加付费会话、不修改宿主配置。

WorkBuddy 默认扫描 WORKBUDDY_HOME 的 projects 与 traces。主文件 `<session>.jsonl` 和 `<session>/subagents/**/*.jsonl` 作为一个逻辑会话，响应 ID 跨文件去重；较新文件的同 ID 修正替换旧记录。trace.modelInfo 与 trace.metadata.modelInfo 的 totalInputTokens／totalOutputTokens 已含缓存；totalCachedTokens 不额外相加。同会话有效明细（含全零修正）会阻止 trace 回填；多个 trace 只取最新有效汇总。当前 SQLite session_usage.used／size 是 context、credit_json 是费用，不读取它们作为 billed token。固定格式证据见 [WorkBuddy parser 与回归](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/test/rollout-parser.test.js) 。

OMP／OmO 汇总 `<cwd>/<session>.jsonl` 与 `<cwd>/<session>/**/*.jsonl`，以最新成员文件选择有效会话。同消息 ID 按文件修改时间及文件内顺序修正替换；没有 ID 的明确计数保留原有读取行为，按文件与记录位置分别统计。标准 sessions 根下主文件缺失时仍合并其子树；自定义 workspace 根由已扫描的主文件关联子树，不读取 roots 外文件。header.parentSession 是不透明 lineage，不跟随该值打开外部文件。OMP reasoningTokens 独立计，OmO reasoning 是 output 子集。依据为 [OMP 官方会话文档](https://github.com/can1357/oh-my-pi/blob/main/docs/session.md) 、[子会话导出文档](https://github.com/can1357/oh-my-pi/blob/main/docs/session-operations-export-share-fork-resume.md) 和固定 [OmO 语义回归](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/test/omo-parser.test.js) 。

2026-10-04 核对 [Cursor 官方 SDK](https://cursor.com/docs/sdk/typescript) 与公开 [@cursor/sdk 1.0.35](https://registry.npmjs.org/@cursor/sdk/1.0.35) ：本地 SDK 存储 sdk-agent-store/index.db 的 runs.usage_json 有明确 input／output／cache／total 计数，reasoning 属于 output 子集。尚未确认 Cursor CLI 使用同一存储；这项发现不等于 CLI reader 已实现。仅下载并检查公开包，没有执行 SDK、创建会话或读取 sdk/auth.json，也未调用需要凭据的 getUsage。官方 CLI output-format／ACP 与 hooks.preCompact 的 context 字段目前没有提供已确认可直接移植的 billed token 来源。

Antigravity 仅读取 gen_metadata 的 protobuf 白名单字段及 transcript 的 type／step_index／created_at；last_step_index + 1 对应已完成 planner。输出 checksum 仅作 text 缺失时的回退，不与 text／reasoning 重复计数；未知 protobuf 内容不解码，SQLite messages／auth 表不查询。Kiro 旧会话通过 SQLite JSON 投影明确计数、模型、时间和 ID；新版日志的字符数与 credits 无法证明 billed token。固定来源测试见 [Antigravity 路径](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/test/antigravity-paths.test.js) 、[Kiro 双安装](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/test/kiro-cli-dual-install.test.js) 和 [rollout parser](https://github.com/xiufengsun/TokenTracker/blob/956e3ab331ce265021ed61c73622a516e882da2e/test/rollout-parser.test.js) 。这些是参考实现格式证据，不是厂商 schema 稳定性保证。

DeepSeek Harness 增加项目依赖 `zstandard>=0.25.0`，Python 3.10／3.11 标准库和现有依赖不能解压 zstd。每个压缩文件限制 64 MiB、解压结果限制 128 MiB；先验证全部帧再投影元数据，不写出解压正文。2026-10-03 核对 [PyPI](https://pypi.org/project/zstandard/) 与 [发布记录](https://github.com/indygreg/python-zstandard/releases/tag/0.25.0) ：最近发布为 2025-09-14；[维护者提交](https://github.com/indygreg/python-zstandard/commits/main/) 最近有人类提交于 2026-07-18，近期更新含 Dependabot。核对的 [issue 345](https://github.com/indygreg/python-zstandard/issues/345) 与 [issue 335](https://github.com/indygreg/python-zstandard/issues/335) 尚无维护者回复，不将机器人活动视为 issue 响应证明。本轮在任务目录安装测试依赖；正式安装通过 pyproject 获取，不依赖 `.tmp/`。

## 验证与未完成项

本轮离线回归覆盖：响应／消息 ID 去重、修正替换、累计快照、Dots 大小写分流、缓存／reasoning 子集、用户正文中的伪 usage、错误／空格式、布尔／非有限数、超过 8 MiB 的日志、截断／重写、Cline 两种 envelope 与导入历史、MiMo 镜像过滤、Science 示例与部分 schema、SQLite 只读字节不变、自定义目录保留 parser，以及 all／auto 去重。

2026-10-03 19:10：44-provider 本机 JSON 冒烟覆盖 registry 全集合，没有 ANSI 控制码／traceback；只有 Codex、Claude、OpenCode 返回本地 token，41 项没有 token，全部未返回账户额度窗口。新增 reader 没有本机有效会话证明，不能把 fixture 当作实机完成。

2026-10-03 19:13：当前工作区完整 pytest 171 项通过，包含既有真实 POSIX PTY 子进程回归；compileall、git diff --check、双语 README／审计文档相对链接、代码围栏与 44 项 registry 映射检查通过。正式运行不依赖 `.tmp/` 中的上游下载或验证摘要。没有提交、推送或发布。

2026-10-03 19:34：本轮新增 Grok／DeepSeek Harness／LM Studio，以及 Copilot 原生／Devin／ZCode 完整格式修复后，全量 pytest 227 项通过。新用例覆盖父计数／独立列、native／OTel 优先、共享 spanContext、分叉／重放、迁移边界、多帧／截断／上限、活动版本及轮转日志；SQLite authorizer 阻止私有列读取。compileall 与 diff 检查通过；再次核查 44 项仍只有 Codex／Claude／OpenCode 返回 token、全部无额度窗口，新增接入只有离线证据。

2026-10-03 19:51：新增 Antigravity 明确 generation metadata 与 Kiro 旧 CLI 会话 reader 后，全量 pytest 248 项通过，含已有 PTY 与控制字符过滤回归；compileall 通过。44-provider JSON 冒烟仍仅 Codex／Claude／OpenCode 返回 token，41 项无 token、全部无额度窗口；新增两项没有真实会话证明。

2026-10-04 01:20：补齐 WorkBuddy 主／子会话树与两种 trace 回退、OMP／OmO 嵌套会话树后，全量 pytest 315 项通过；本检查点新增 44 项离线回归，覆盖跨文件去重／修正、trace 镜像与明细优先、孤立子树、截断、未知正文／凭据拒读、无效计数、只读和自定义 roots。compileall 与 diff 检查通过；44-provider JSON 冒烟仍只有 Codex／Claude／OpenCode 返回 token，41 项无 token、全部无额度窗口。当前本机 kiro-cli 2.2.2 的版本命令仅验证安装版本，没有生成或验证新版计费会话。新增适配仍无真实会话／宿主证明，未提交或推送。

下一步仍属于本 Goal：核对新版 Kiro CLI 和 Cursor CLI 是否存在不读凭据的可靠 token 来源，确认 Cursor SDK 与 CLI 存储关系；补足其他 reader 的 subagent／跨版本／实机会话证据。Kiro 字符估算与 credits 不转换为 token。已核对的 [Cursor CLI output format](https://cursor.com/docs/cli/reference/output-format) 成功结果字段、[ACP](https://cursor.com/docs/cli/acp) 和 [hooks](https://cursor.com/docs/hooks) 未提供可据以实现的 billed token 计数协议；这不证明本地不存在其他可靠来源。GUI-only 数据源另列状态，不替代这些终端要求。Goal 工具本轮仍返回 usageLimited；按用户继续指令完成本检查点，未创建替代 Goal，完整目标未标记完成。
