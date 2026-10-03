from __future__ import annotations

import math
import os
import shutil
import time
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from .models import RateWindow, Snapshot, as_float


RESET = "\033[0m"


@dataclass(frozen=True)
class Theme:
    name: str
    colors: dict[str, str]
    error: str


THEMES = {
    "catppuccin-mocha": Theme("catppuccin-mocha", {"codex": "\033[38;2;137;180;250m", "claude": "\033[38;2;203;166;247m", "kimi": "\033[38;2;166;227;161m"}, "\033[38;2;243;139;168m"),
    "nord": Theme("nord", {"codex": "\033[38;2;136;192;208m", "claude": "\033[38;2;180;142;173m", "kimi": "\033[38;2;163;190;140m"}, "\033[38;2;191;97;106m"),
    "dracula": Theme("dracula", {"codex": "\033[38;2;139;233;253m", "claude": "\033[38;2;255;121;198m", "kimi": "\033[38;2;80;250;123m"}, "\033[38;2;255;85;85m"),
    "default": Theme("default", {"codex": "\033[36m", "claude": "\033[35m", "kimi": "\033[32m"}, "\033[31m"),
}
PROGRESS_STYLES = {
    "blocks": ("█", "░"),
    "ascii": ("#", "."),
    "thin": ("▓", "·"),
    "dots": ("●", "○"),
}


def get_theme(name: str | None = None) -> Theme:
    selected = name or os.environ.get("AI_CLI_STATUSLINE_THEME", "catppuccin-mocha")
    try:
        return THEMES[selected.lower()]
    except KeyError as exc:
        available = ", ".join(sorted(THEMES))
        raise ValueError(f"未知主题：{selected}；可选：{available}") from exc


def bar(percent: float | None, width: int = 10, style: str | None = None) -> str:
    selected = style or os.environ.get("AI_CLI_STATUSLINE_PROGRESS_STYLE", "blocks")
    try:
        filled_glyph, empty_glyph = PROGRESS_STYLES[selected.lower()]
    except KeyError as exc:
        available = ", ".join(sorted(PROGRESS_STYLES))
        raise ValueError(f"未知进度样式：{selected}；可选：{available}") from exc
    percent = as_float(percent)
    if percent is None:
        return "?" + empty_glyph * (width - 1)
    filled = round(max(0.0, min(100.0, percent)) * width / 100)
    return filled_glyph * filled + empty_glyph * (width - filled)


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


def _limit_text(window: RateWindow, progress_style: str | None = None) -> str:
    percent = as_float(window.used_percent)
    if percent is not None:
        percent = max(0.0, min(100.0, percent))
    used = "?" if percent is None else f"{percent:g}%"
    text = f"{window.label} {bar(percent, style=progress_style)} {used} used"
    reset = as_float(window.resets_at)
    if reset is not None and reset > 0:
        minutes = math.ceil((reset - time.time()) / 60)
        if minutes <= 0:
            text += " reset due"
        elif minutes >= 1440:
            text += f" reset in {minutes // 1440}d {(minutes % 1440) // 60}h"
        elif minutes >= 60:
            text += f" reset in {minutes // 60}h {minutes % 60}m"
        else:
            text += f" reset in {minutes}m"
    return text


def render_snapshot(snapshot: Snapshot, color: bool = True, theme: Theme | None = None, progress_style: str | None = None) -> str:
    palette = theme or get_theme()
    has_data = (
        snapshot.model is not None
        or snapshot.tokens is not None
        or snapshot.context_percent is not None
        or bool(snapshot.rate_limits)
    )
    if snapshot.error and not has_data:
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
            parts.append(f"ctx {bar(snapshot.context_percent, style=progress_style)} {snapshot.context_percent:.0f}% used")
        parts.extend(_limit_text(window, progress_style=progress_style) for window in snapshot.rate_limits)
        if snapshot.error:
            parts.append(snapshot.error)
        body = " · ".join(parts)
    # Log metadata must never act as terminal escape sequences or extra rows.
    body = "".join(" " if unicodedata.category(char) in {"Cc", "Cf", "Cs"} else char for char in body)
    if color:
        prefix = palette.error if snapshot.error else palette.colors.get(snapshot.provider, "")
        return f"{prefix}{body}{RESET}"
    return body


def render_line(snapshots: Iterable[Snapshot], color: bool = True, theme: Theme | None = None, progress_style: str | None = None) -> str:
    palette = theme or get_theme()
    return "  │  ".join(render_snapshot(snapshot, color=color, theme=palette, progress_style=progress_style) for snapshot in snapshots)


def _wrap_cells(text: str, width: int) -> list[str]:
    """Wrap plain terminal text, including wide Chinese characters."""
    width = max(2, width)
    rows: list[str] = []
    line = ""
    cells = 0
    for char in text:
        size = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1)
        if cells + size > width:
            rows.append(line.rstrip())
            line = ""
            cells = 0
        if not line and char == " ":
            continue
        line += char
        cells += size
    if line:
        rows.append(line.rstrip())
    return rows


def render_watch(snapshots: Iterable[Snapshot], width: int, color: bool = True, theme: Theme | None = None, progress_style: str | None = None) -> str:
    palette = theme or get_theme()
    rows: list[str] = []
    for snapshot in snapshots:
        body = render_snapshot(snapshot, color=False, theme=palette, progress_style=progress_style)
        prefix = palette.error if snapshot.error else palette.colors.get(snapshot.provider, "")
        for row in _wrap_cells(body, width):
            rows.append(f"{prefix}{row}{RESET}" if color else row)
    return "\n".join(rows)


def clear_screen() -> None:
    if os.environ.get("TERM") != "dumb":
        print("\033[2J\033[H", end="")


def terminal_width(default: int = 120) -> int:
    return shutil.get_terminal_size((default, 24)).columns
