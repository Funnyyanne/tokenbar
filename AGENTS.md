# ai-cli-statusline

本项目是本地优先的多 AI CLI 用量状态栏工具，当前支持 Codex、Claude Code 和可配置的 Kimi Code 日志扫描适配器。

## 边界

- 只读取本机 CLI 的状态数据库、转录日志或 app-server 只读接口。
- 不读取、打印或提交认证凭据、完整提示词和完整回复内容。
- 真实账户额度只在来源明确返回时显示；来源不可用时显示错误状态。
- 未安装或没有可识别日志的 CLI 只做离线适配，不宣称实时验证完成。

## 验证入口

```bash
python3 -m pytest
python3 -m ai_cli_statusline status --providers codex,claude,kimi --no-color
python3 -m ai_cli_statusline watch --providers codex,claude,kimi
```

实现细节和当前验证状态见 `README.md` 与 `ROADMAP.md`。
