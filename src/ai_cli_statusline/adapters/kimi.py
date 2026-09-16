from __future__ import annotations

from pathlib import Path

from .jsonl import JsonlAdapter, configured_roots


class KimiAdapter(JsonlAdapter):
    provider = "kimi"
    label = "Kimi"

    def __init__(self, roots: list[Path] | None = None, max_bytes: int = 8 * 1024 * 1024) -> None:
        if roots is None:
            roots = configured_roots(
                "KIMI_CODE_HOME",
                [Path.home() / ".kimi-code", Path.home() / ".kimi", Path.home() / ".config" / "kimi"],
            )
        super().__init__(self.provider, self.label, roots, patterns=("wire.jsonl", "*.jsonl", "*.json"), max_bytes=max_bytes)
