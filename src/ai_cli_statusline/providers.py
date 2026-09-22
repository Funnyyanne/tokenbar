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
    "gemini": ProviderSpec("gemini", "Gemini", "experimental", "generic-jsonl", (HOME / ".gemini",)),
    "antigravity": ProviderSpec("antigravity", "Antigravity", "experimental", "generic-jsonl", (HOME / ".gemini" / "antigravity", HOME / ".gemini" / "antigravity-cli")),
    "deepseek": ProviderSpec("deepseek", "Deepseek", "experimental", "generic-jsonl", (HOME / ".dsh" / "sessions",)),
    "pi": ProviderSpec("pi", "Pi", "experimental", "generic-jsonl", (HOME / ".pi" / "agent" / "sessions",)),
    "omp": ProviderSpec("omp", "Omp", "experimental", "generic-jsonl", (HOME / ".omp" / "agent" / "sessions",)),
    "omo": ProviderSpec("omo", "Omo", "experimental", "generic-jsonl", (HOME / ".omo" / "agent" / "sessions",)),
    "craft": ProviderSpec("craft", "Craft", "experimental", "generic-jsonl", (HOME / ".craft-agent",)),
    "reasonix": ProviderSpec("reasonix", "Reasonix", "experimental", "generic-jsonl", (HOME / ".reasonix",)),
    "goose": ProviderSpec("goose", "Goose", "planned", "unavailable", (HOME / ".local" / "share" / "goose",), "需要专用 sessions.db reader"),
    "roo": ProviderSpec("roo", "Roo", "planned", "unavailable", (HOME / "Library" / "Application Support" / "Code" / "User" / "globalStorage",), "需要限定 Roo 扩展数据源的专用 reader"),
    "lmstudio": ProviderSpec("lmstudio", "Lmstudio", "planned", "unavailable", (HOME / ".lmstudio" / "server-logs",), "需要专用 .log reader"),
    "cursor": ProviderSpec("cursor", "Cursor", "experimental", "cursor", (HOME / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage", HOME / ".config" / "Cursor" / "User" / "globalStorage"), "隐私限制：已知用量方案需要读取认证 token 并调用远端接口"),
    "copilot": ProviderSpec("copilot", "Copilot", "planned", "unavailable", (HOME / ".copilot",), "需要专用 session-store／OTEL reader"),
    "kilo": ProviderSpec("kilo", "Kilo", "planned", "unavailable", (HOME / ".local" / "share" / "kilo",), "需要专用 OpenCode schema reader"),
    "zed": ProviderSpec("zed", "Zed", "planned", "unavailable", (HOME / ".local" / "share" / "zed",), "需要专用 threads.db reader"),
    "qoder": ProviderSpec("qoder", "Qoder", "planned", "unavailable", (HOME / "Library" / "Application Support" / "Qoder",), "需要专用 token_info reader"),
    "anythingllm": ProviderSpec("anythingllm", "Anythingllm", "planned", "unavailable", (HOME / "Library" / "Application Support" / "anythingllm-desktop",), "需要专用 message metrics reader"),
    "devin": ProviderSpec("devin", "Devin", "planned", "unavailable", (HOME / ".local" / "share" / "devin",), "需要专用 sessions.db reader"),
    "mimo": ProviderSpec("mimo", "Mimo", "planned", "unavailable", (HOME / ".local" / "share" / "mimocode",), "需要专用 OpenCode schema reader"),
    "zcode": ProviderSpec("zcode", "Zcode", "planned", "unavailable", (HOME / ".zcode",), "需要专用 OpenCode schema reader"),
}


def auto_provider_names() -> list[str]:
    return [name for name, spec in PROVIDER_SPECS.items() if spec.maturity == "stable"]
