from ai_cli_statusline.models import RateWindow, Snapshot
import unicodedata

import pytest

from ai_cli_statusline.render import bar, get_theme, render_line, render_watch


def test_bar_clamps_and_rounds():
    assert bar(0) == "░░░░░░░░░░"
    assert bar(50) == "█████░░░░░"
    assert bar(120) == "██████████"


def test_render_snapshot_contains_usage_and_limit():
    snapshot = Snapshot(
        provider="codex",
        label="Codex",
        model="gpt-5.6-sol",
        tokens=12345,
        input_tokens=12000,
        output_tokens=345,
        context_used=25000,
        context_window=100000,
        rate_limits=[RateWindow("5h", 27)],
    )
    rendered = render_line([snapshot], color=False)
    assert "Codex" in rendered
    assert "12.3k" in rendered
    assert "ctx" in rendered
    assert "5h" in rendered
    assert "███░░░░░░░" in rendered


def test_theme_palette_is_selectable():
    snapshot = Snapshot(provider="claude", label="Claude", tokens=10)
    rendered = render_line([snapshot], color=True, theme=get_theme("dracula"))
    assert "\x1b[38;2;255;121;198m" in rendered


def test_text_progress_styles_are_selectable():
    assert bar(50, style="ascii") == "#####....."
    assert bar(50, style="thin") == "▓▓▓▓▓·····"
    assert bar(50, style="dots") == "●●●●●○○○○○"


@pytest.mark.parametrize("percent", [None, float("nan"), float("inf"), float("-inf")])
def test_nonfinite_progress_is_unknown(percent):
    rendered = render_line([Snapshot("codex", "Codex", rate_limits=[RateWindow("5h", percent)])], color=False)
    assert "?░░░░░░░░░" in rendered
    assert "? used" in rendered
    assert "nan" not in rendered and "inf" not in rendered


@pytest.mark.parametrize("percent,expected", [(-5, "0%"), (120, "100%")])
def test_limit_percentage_matches_clamped_bar(percent, expected):
    rendered = render_line([Snapshot("codex", "Codex", rate_limits=[RateWindow("5h", percent)])], color=False)
    assert f"{expected} used" in rendered


@pytest.mark.parametrize("remaining,expected", [(90, "2m"), (3601, "1h 1m"), (93600, "1d 2h"), (0, "due"), (-60, "due")])
def test_limit_reset_countdown(remaining, expected, monkeypatch):
    monkeypatch.setattr("ai_cli_statusline.render.time.time", lambda: 100_000)
    rendered = render_line([Snapshot("codex", "Codex", rate_limits=[RateWindow("5h", 27, 100_000 + remaining)])], color=False)
    assert "reset " + ("due" if expected == "due" else f"in {expected}") in rendered
    assert "27% used" in rendered


@pytest.mark.parametrize("reset", [None, 0, -1, float("nan"), float("inf")])
def test_invalid_reset_time_is_not_displayed(reset):
    rendered = render_line([Snapshot("codex", "Codex", rate_limits=[RateWindow("5h", 27, reset)])], color=False)
    assert "reset" not in rendered


def test_watch_wraps_wide_text_and_keeps_each_provider(monkeypatch):
    snapshots = [Snapshot("codex", "Codex", tokens=12345), Snapshot.unavailable("kimi", "Kimi", "没有可识别用量" * 10)]
    rendered = render_watch(snapshots, width=32, color=False)
    assert "Codex" in rendered and "Kimi unavailable" in rendered
    for row in rendered.splitlines():
        assert sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in {"W", "F"} else 1 for c in row) <= 32
    assert "\x1b" not in rendered


def test_log_metadata_cannot_control_terminal():
    rendered = render_line([Snapshot("codex", "Codex", model="fake\x1b[2J\nmodel\t\x07")], color=False)
    assert "\x1b" not in rendered and "\x07" not in rendered
    assert "\n" not in rendered and "\t" not in rendered


@pytest.mark.parametrize("used,window", [(-1, 100), (1, 0), (1, -100), (None, 100), (1, None)])
def test_context_without_valid_counts_has_no_progress(used, window):
    snapshot = Snapshot("kimi", "Kimi", context_used=used, context_window=window)
    assert snapshot.context_percent is None
    assert "ctx" not in render_line([snapshot], color=False)
