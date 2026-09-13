from __future__ import annotations

import datetime as dt
import os
import shutil
from typing import Iterable

from .models import RateWindow, Snapshot


RESET = "\033[0m"
COLORS = {"codex": "\033[36m", "claude": "\033[35m", "kimi": "\033[32m"}


def bar(percent: float | None, width: int = 10) -> str:
    if percent is None:
        return "?" + "░" * (width - 1)
    filled = round(max(0.0, min(100.0, percent)) * width / 100)
    return "█" * filled + "░" * (width - filled)


def compact_number(value: int | None) -> str:
    if value is None:
        return "?"
    amount = abs(value)
    if amount >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:,}"


def _limit_text(window: RateWindow) -> str:
    used = "?" if window.used_percent is None else f"{window.used_percent:g}%"
    remaining = None if window.used_percent is None else 100 - window.used_percent
    return f"{window.label} {bar(remaining)} {used} used"


def render_snapshot(snapshot: Snapshot, color: bool = True) -> str:
    if snapshot.error:
        body = f"{snapshot.label} unavailable ({snapshot.error})"
    else:
        parts = [snapshot.label]
        if snapshot.model:
            parts.append(snapshot.model)
        if snapshot.tokens is not None:
            parts.append(f"total {compact_number(snapshot.tokens)}")
        if snapshot.input_tokens is not None or snapshot.output_tokens is not None:
            parts.append(f"in {compact_number(snapshot.input_tokens)} / out {compact_number(snapshot.output_tokens)}")
        if snapshot.context_percent is not None:
            parts.append(f"ctx {bar(100 - snapshot.context_percent)} {snapshot.context_percent:.0f}% used")
        parts.extend(_limit_text(window) for window in snapshot.rate_limits)
        body = " · ".join(parts)
    if color:
        return f"{COLORS.get(snapshot.provider, '')}{body}{RESET}"
    return body


def render_line(snapshots: Iterable[Snapshot], color: bool = True) -> str:
    return "  │  ".join(render_snapshot(snapshot, color=color) for snapshot in snapshots)


def clear_screen() -> None:
    if os.environ.get("TERM") != "dumb":
        print("\033[2J\033[H", end="")


def terminal_width(default: int = 120) -> int:
    return shutil.get_terminal_size((default, 24)).columns
