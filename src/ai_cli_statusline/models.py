from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class RateWindow:
    label: str
    used_percent: float | None = None
    resets_at: float | None = None


@dataclass(slots=True)
class Snapshot:
    provider: str
    label: str
    maturity: str = "stable"
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model: str | None = None
    tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    context_used: int | None = None
    context_window: int | None = None
    rate_limits: list[RateWindow] = field(default_factory=list)
    source: str | None = None
    error: str | None = None
    stale: bool = False

    @property
    def context_percent(self) -> float | None:
        if self.context_used is None or not self.context_window:
            return None
        return max(0.0, min(100.0, self.context_used * 100 / self.context_window))

    @classmethod
    def unavailable(
        cls,
        provider: str,
        label: str,
        error: str,
        source: str | None = None,
        *,
        maturity: str = "stable",
    ) -> "Snapshot":
        return cls(provider=provider, label=label, maturity=maturity, error=error, source=source)


def as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None
