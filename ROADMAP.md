# ROADMAP

## 当前状态

- 已完成：可信多 CLI 用量接入 Goal 已消除 SQLite 凭据误读、伪 token、缓存／长会话错误和不实 provider 支持声明；验收与支持矩阵见 [Provider 支持审计](docs/provider-support-audit.md) 。
- stable：Codex、Claude Code、Kimi Code、OpenCode；`--providers auto` 只包含这些有专用 reader／协议与回归证据的 provider。
- experimental：Gemini、Pi、OMP、Goose、Roo、Copilot、Kilo、Zed、AnythingLLM、Devin、ZCode 有 provider-specific reader，必须显式启用；Zed 仅支持未压缩旧线程，Copilot 需要先启用官方 OTel 文件导出。
- 受限／planned：Cursor 因凭据边界只返回受限原因；Antigravity、DeepSeek、OmO、Craft、Reasonix、LM Studio、Qoder、MiMo 缺少满足准确性与隐私门槛的本地 token schema，不再用通用 JSONL 或相似 schema 猜测。
- 待确认：本机已安装 Kimi Code 2.0.0，但当前没有可识别会话且未配置 `status_line`，无法完成真实 TUI 重载验证；真实 Claude／Kimi 额度仍依赖官方状态栏快照或本地会话字段。
- 待确认：当前沙箱中 Codex 本地 token 读取正常，但 app-server 额度 RPC 提前退出；不将离线回归冒充实时额度验证。

## 最近完成

- 2026-10-01 17:44 交付：修复 Zed 仅扫描最新 20 条线程导致漏计／错误 unavailable 的回归，逐行统计所有可识别 JSON 线程；恢复 Gemini、Pi、OMP 专用 reader 对 `AI_CLI_STATUSLINE_SOURCES` 的目录优先配置，并同步双语使用说明。

- 2026-09-29 08:41 交付：复核并收紧 OpenCode、ZCode、Zed、AnythingLLM／Devin SQLite reader 的只读连接生命周期，连接初始化失败时安全跳过；未改变 provider 字段白名单与隐私边界。
- 2026-09-28 23:21 交付：重新核实 Claude／Codex 之外的 provider；新增 Gemini、Pi／OMP、Copilot OTel 专用 reader，修复 OpenCode 旧 schema 实机不可读、AnythingLLM／Devin 正文列读取和 ZCode cache／reasoning 双计；证据不足的 8 个 provider 降级为 planned／受限。
- 2026-09-23 22:30 交付：为 Goose、Roo、LM Studio、Copilot、Kilo、Zed、Qoder、AnythingLLM、Devin、MiMo、ZCode 接入实验性专用 reader；Qoder 仅接受明确 usage 对象，避免将 credits 或认证信息冒充 token；新增合成 SQLite／JSON fixture 与失败隔离回归测试。

- 2026-09-19 09:07 交付：完成可信多 CLI 用量接入 Goal；SQLite 改为正向字段白名单，修复 Codex 部分失败／多库回退、缓存合并／TTL／并发写、8 MiB JSONL 尾部读取限制和 CLI 失败隔离；新增 OpenCode 专用 reader、Cursor 隐私受限 adapter、provider 成熟度注册和支持审计。
- 2026-09-23 21:28 交付：修复长 JSONL 全量读取、Codex 空 token 数据库回退和无数据状态错误成功码；46 项测试通过。
- 2026-09-18 00:21 交付：修复 Kimi `[status_line]` 表头尾随注释导致重复表的问题，写回前验证 TOML；JSONL 扫描不再因 50 个较新无用量文件遗漏有效会话。
- 2026-09-17 23:58 交付：应用 Kimi 配置修复 patch，补强 Codex 状态数据库选择、文件扫描竞态、SQLite 汇总和缓存测试隔离；23 项测试通过。
- 2026-09-17 23:10 交付：修复已有 `[status_line]` 段缺少 `command` 时的 TOML 插入位置，避免 `setup kimi --force` 生成无效配置；17 项测试通过。
- 2026-09-17 22:55 交付：接入 Kimi Code `usage.record` 的 `inputOther`、`output`、`inputCacheRead` 和 `inputCacheCreation` 字段；15 项测试通过。
- 2026-09-17 01:07 交付：重构 Claude/Kimi JSONL 解析、增加状态栏缓存和 `setup` 配置命令，扩展 JSONL／SQLite provider、主题和纯文本进度样式；14 项测试通过。
- 2026-09-14 00:15 交付：增加 `integrate claude|kimi|codex` 配置说明、Claude/Kimi stdin 状态栏命令和 5 项离线测试；测试通过。
- 2026-09-14 交付：创建 `tokenbar` 独立项目骨架、只读适配器、统一渲染器和离线测试。

## 最近验证

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
