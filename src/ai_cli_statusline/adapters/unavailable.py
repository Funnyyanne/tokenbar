from __future__ import annotations

from pathlib import Path

from .base import Adapter
from ..models import Snapshot


class UnavailableAdapter(Adapter):
    """Represent a known provider that has no verified safe reader yet."""

    def __init__(self, provider: str, label: str, roots: tuple[Path, ...], maturity: str, reason: str) -> None:
        self.provider = provider
        self.label = label
        self.roots = roots
        self.maturity = maturity
        self.reason = reason

    def snapshot(self) -> Snapshot:
        return Snapshot.unavailable(
            self.provider,
            self.label,
            self.reason,
            ", ".join(map(str, self.roots)) or None,
            maturity=self.maturity,
        )
