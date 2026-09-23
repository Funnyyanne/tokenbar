from __future__ import annotations

from pathlib import Path

from .jsonl import JsonlAdapter


class GenericCliAdapter(JsonlAdapter):
    def __init__(self, provider: str, roots: list[Path], maturity: str = "experimental") -> None:
        label = provider.replace("-", " ").replace("_", " ").title()
        super().__init__(provider, label, roots, patterns=("wire.jsonl", "*.jsonl", "*.json"), maturity=maturity)
