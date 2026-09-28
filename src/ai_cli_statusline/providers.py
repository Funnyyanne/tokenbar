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
    "goose": ProviderSpec("goose", "Goose", "experimental", "sqlite", (HOME / ".local" / "share" / "goose",)),
    "roo": ProviderSpec("roo", "Roo", "experimental", "json", (HOME / ".roo", HOME / "Library" / "Application Support" / "Code" / "User" / "globalStorage")),
    "lmstudio": ProviderSpec("lmstudio", "LM Studio", "experimental", "json", (HOME / ".lmstudio" / "server-logs",)),
    "cursor": ProviderSpec("cursor", "Cursor", "experimental", "cursor", (HOME / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage", HOME / ".config" / "Cursor" / "User" / "globalStorage"), "隐私限制：已知用量方案需要读取认证 token 并调用远端接口"),
    "copilot": ProviderSpec("copilot", "Copilot", "experimental", "json", (HOME / ".copilot",)),
    "kilo": ProviderSpec("kilo", "Kilo", "experimental", "sqlite", (HOME / ".local" / "share" / "kilo",)),
    "zed": ProviderSpec("zed", "Zed", "experimental", "sqlite", (HOME / ".local" / "share" / "zed",)),
    "qoder": ProviderSpec("qoder", "Qoder", "experimental", "json", (HOME / ".qoder" / "projects", HOME / ".qoderwork" / "projects", HOME / "Library" / "Application Support" / "Qoder")),
    "anythingllm": ProviderSpec("anythingllm", "AnythingLLM", "experimental", "sqlite", (HOME / "Library" / "Application Support" / "anythingllm-desktop", HOME / ".anythingllm")),
    "devin": ProviderSpec("devin", "Devin", "experimental", "sqlite", (HOME / ".local" / "share" / "devin", HOME / "Library" / "Application Support" / "devin")),
    "mimo": ProviderSpec("mimo", "MiMo", "experimental", "sqlite", (HOME / ".local" / "share" / "mimocode",)),
    "zcode": ProviderSpec("zcode", "ZCode", "experimental", "sqlite", (HOME / ".zcode",)),
}


def auto_provider_names() -> list[str]:
    return [name for name, spec in PROVIDER_SPECS.items() if spec.maturity == "stable"]
