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
    "antigravity": ProviderSpec("antigravity", "Antigravity", "planned", "unavailable", reason="未找到公开且稳定的本地 token schema"),
    "deepseek": ProviderSpec("deepseek", "DeepSeek", "planned", "unavailable", reason="未确认 .dsh 为官方 CLI token 数据源"),
    "pi": ProviderSpec("pi", "Pi", "experimental", "pi", (HOME / ".pi" / "agent" / "sessions",)),
    "omp": ProviderSpec("omp", "OMP", "experimental", "omp", (HOME / ".omp" / "agent" / "sessions",)),
    "omo": ProviderSpec("omo", "OmO", "planned", "unavailable", reason="未确认独立 CLI 与公开 token schema"),
    "craft": ProviderSpec("craft", "Craft", "planned", "unavailable", reason="未找到可验证的本地 token schema"),
    "reasonix": ProviderSpec("reasonix", "Reasonix", "planned", "unavailable", reason="未找到可验证的本地 token schema"),
    "goose": ProviderSpec("goose", "Goose", "experimental", "sqlite", (HOME / ".local" / "share" / "goose",)),
    "roo": ProviderSpec("roo", "Roo", "experimental", "json", (HOME / ".roo", HOME / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline", HOME / ".config" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline")),
    "lmstudio": ProviderSpec("lmstudio", "LM Studio", "planned", "unavailable", reason="官方 API 响应含 usage，但未确认安全、持久的本地 token 日志"),
    "cursor": ProviderSpec("cursor", "Cursor", "experimental", "cursor", (HOME / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage", HOME / ".config" / "Cursor" / "User" / "globalStorage"), "隐私限制：已知用量方案需要读取认证 token 并调用远端接口"),
    "copilot": ProviderSpec("copilot", "Copilot", "experimental", "otel", (HOME / ".copilot" / "otel",)),
    "kilo": ProviderSpec("kilo", "Kilo", "experimental", "sqlite", (HOME / ".local" / "share" / "kilo",)),
    "zed": ProviderSpec("zed", "Zed", "experimental", "sqlite", (HOME / ".local" / "share" / "zed",)),
    "qoder": ProviderSpec("qoder", "Qoder", "planned", "unavailable", reason="官方 /usage 提供 credits，未确认本地 token 字段"),
    "anythingllm": ProviderSpec("anythingllm", "AnythingLLM", "experimental", "sqlite", (HOME / "Library" / "Application Support" / "anythingllm-desktop", HOME / ".anythingllm")),
    "devin": ProviderSpec("devin", "Devin", "experimental", "sqlite", (HOME / ".local" / "share" / "devin", HOME / "Library" / "Application Support" / "devin")),
    "mimo": ProviderSpec("mimo", "MiMo", "planned", "unavailable", reason="仅确认本地 SQLite 目录，未从官方源码确认 token 表结构"),
    "zcode": ProviderSpec("zcode", "ZCode", "experimental", "sqlite", (HOME / ".zcode",)),
}


def auto_provider_names() -> list[str]:
    return [name for name, spec in PROVIDER_SPECS.items() if spec.maturity == "stable"]
