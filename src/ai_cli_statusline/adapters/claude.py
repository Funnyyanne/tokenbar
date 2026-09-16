from __future__ import annotations

from pathlib import Path

from .jsonl import JsonlAdapter, configured_roots


class ClaudeAdapter(JsonlAdapter):
    provider = "claude"
    label = "Claude"

    def __init__(self, roots: list[Path] | None = None, max_bytes: int = 8 * 1024 * 1024) -> None:
        roots = roots or [configured_roots("CLAUDE_CONFIG_DIR", [Path.home() / ".claude"])[0] / "projects"]
        super().__init__(self.provider, self.label, roots, max_bytes=max_bytes)
