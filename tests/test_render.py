from ai_cli_statusline.models import RateWindow, Snapshot
from ai_cli_statusline.render import bar, get_theme, render_line


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
