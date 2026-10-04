from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    name: str
    label: str
    maturity: str
    reader: str
    roots: tuple[Path, ...] = ()
    reason: str | None = None


HOME = Path.home()

PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "codex": ProviderSpec("codex", "Codex", "stable", "codex"),
    "claude": ProviderSpec("claude", "Claude", "stable", "claude"),
    "kimi": ProviderSpec("kimi", "Kimi", "stable", "kimi"),
    "opencode": ProviderSpec("opencode", "OpenCode", "stable", "opencode", (HOME / ".local" / "share" / "opencode", HOME / ".opencode")),
    "gemini": ProviderSpec("gemini", "Gemini", "experimental", "gemini", (HOME / ".gemini" / "tmp",)),
    "antigravity": ProviderSpec("antigravity", "Antigravity", "experimental", "antigravity", tuple(HOME / ".gemini" / name / "conversations" for name in ("antigravity", "antigravity-ide", "antigravity-cli"))),
    "deepseek": ProviderSpec("deepseek", "DeepSeek", "experimental", "deepseek", (HOME / ".dsh" / "sessions",)),
    "pi": ProviderSpec("pi", "Pi", "experimental", "pi", (HOME / ".pi" / "agent" / "sessions",)),
    "omp": ProviderSpec("omp", "OMP", "experimental", "omp", (HOME / ".omp" / "agent" / "sessions",)),
    "omo": ProviderSpec("omo", "OmO", "experimental", "omo", (HOME / ".omo" / "agent" / "sessions",)),
    "dots": ProviderSpec("dots", "Dots", "experimental", "dots", (HOME / ".pi" / "agent" / "sessions",)),
    "prime": ProviderSpec("prime", "Prime Agent", "experimental", "prime", (HOME / ".prime" / "agent" / "sessions",)),
    "minimax": ProviderSpec("minimax", "MiniMax Code", "experimental", "minimax", (HOME / ".minimax" / "v2" / "sessions",)),
    "codebuddy": ProviderSpec("codebuddy", "CodeBuddy", "experimental", "codebuddy", (HOME / ".codebuddy" / "projects",)),
    "workbuddy": ProviderSpec("workbuddy", "WorkBuddy", "experimental", "workbuddy", (HOME / ".workbuddy" / "projects", HOME / ".workbuddy" / "traces")),
    "commandcode": ProviderSpec("commandcode", "Command Code", "experimental", "commandcode", (HOME / ".commandcode" / "projects",)),
    "openclaw": ProviderSpec("openclaw", "OpenClaw", "experimental", "openclaw", (HOME / ".openclaw" / "agents",)),
    "droid": ProviderSpec("droid", "Droid", "experimental", "droid", (HOME / ".factory" / "sessions",)),
    "hermes": ProviderSpec("hermes", "Hermes", "experimental", "hermes", (HOME / ".hermes",)),
    "claudescience": ProviderSpec("claudescience", "Claude Science", "experimental", "claudescience", (HOME / ".claude-science",)),
    "cline": ProviderSpec("cline", "Cline", "experimental", "cline", (HOME / ".cline" / "data" / "sessions",)),
    "astudio": ProviderSpec("astudio", "AStudio", "experimental", "astudio", (HOME / ".acode" / "sessions", HOME / ".acode" / "archived_sessions")),
    "everycode": ProviderSpec("everycode", "Every Code", "experimental", "everycode", (HOME / ".code" / "sessions",)),
    "grok": ProviderSpec("grok", "Grok Build", "experimental", "grok", (HOME / ".grok" / "sessions",)),
    "kiro": ProviderSpec("kiro", "Kiro", "experimental", "kiro", (HOME / ".kiro" / "sessions",), "仅支持旧 CLI 会话的明确 token 字段；新版字符／credits 不作为 token"),
    "craft": ProviderSpec("craft", "Craft", "planned", "unavailable", reason="尚未实现经验证的 Craft 专用 token reader"),
    "reasonix": ProviderSpec("reasonix", "Reasonix", "experimental", "reasonix", (HOME / ".reasonix",)),
    "goose": ProviderSpec("goose", "Goose", "experimental", "sqlite", (HOME / ".local" / "share" / "goose",)),
    "roo": ProviderSpec("roo", "Roo", "experimental", "json", (HOME / ".roo", HOME / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline", HOME / ".config" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline")),
    "lmstudio": ProviderSpec("lmstudio", "LM Studio", "experimental", "lmstudio", (HOME / ".lmstudio" / "server-logs",)),
    "cursor": ProviderSpec("cursor", "Cursor", "experimental", "cursor", (HOME / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage", HOME / ".config" / "Cursor" / "User" / "globalStorage"), "隐私限制：已知用量方案需要读取认证 token 并调用远端接口"),
    "copilot": ProviderSpec("copilot", "Copilot", "experimental", "copilot", (HOME / ".copilot", HOME / ".copilot-otel")),
    "kilo": ProviderSpec("kilo", "Kilo", "experimental", "sqlite", (HOME / ".local" / "share" / "kilo",)),
    "kilocode": ProviderSpec("kilocode", "Kilo Code", "planned", "unavailable", reason="尚未实现 Kilo Code 扩展 ui_messages 专用 reader；kilo 仅支持 CLI 数据库"),
    "zed": ProviderSpec("zed", "Zed", "experimental", "sqlite", (HOME / ".local" / "share" / "zed",)),
    "qoder": ProviderSpec("qoder", "Qoder", "experimental", "qoder", (HOME / ".qoder" / "projects",)),
    "qodercn": ProviderSpec("qodercn", "Qoder CN", "experimental", "qodercn", (HOME / ".qoder-cn" / "projects",)),
    "anythingllm": ProviderSpec("anythingllm", "AnythingLLM", "experimental", "sqlite", (HOME / "Library" / "Application Support" / "anythingllm-desktop", HOME / ".anythingllm")),
    "devin": ProviderSpec("devin", "Devin", "experimental", "devin", (HOME / ".local" / "share" / "devin" / "cli",)),
    "mimo": ProviderSpec("mimo", "MiMo", "experimental", "mimo", (HOME / ".local" / "share" / "mimocode",)),
    "zcode": ProviderSpec("zcode", "ZCode", "experimental", "zcode", (HOME / ".zcode" / "cli" / "db",)),
    "unsloth": ProviderSpec("unsloth", "Unsloth Studio", "planned", "unavailable", reason="尚未实现 Unsloth Studio 专用 metadata reader"),
    "trae": ProviderSpec("trae", "TRAE", "planned", "unavailable", reason="尚未实现 TRAE 本地用量 reader；不会读取认证凭据"),
    "traecn": ProviderSpec("traecn", "TRAE Work CN", "planned", "unavailable", reason="已知参考方案需要读取认证凭据并请求内部 API，超出本项目隐私边界"),
}


def auto_provider_names() -> list[str]:
    return [name for name, spec in PROVIDER_SPECS.items() if spec.maturity == "stable"]
