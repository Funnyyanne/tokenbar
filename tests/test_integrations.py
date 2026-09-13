from __future__ import annotations

from ai_cli_statusline.integrations import snapshot_from_statusline


def test_claude_statusline_snapshot() -> None:
    snapshot = snapshot_from_statusline(
        "claude",
        "Claude",
        {
            "model": {"display_name": "Sonnet"},
            "context_window": {
                "used_percentage": 25,
                "context_window_size": 200_000,
                "current_usage": {"input_tokens": 10_000, "output_tokens": 500},
            },
            "rate_limits": {"five_hour": {"used_percentage": 40}},
        },
    )
    assert snapshot.model == "Sonnet"
    assert snapshot.context_used == 50_000
    assert snapshot.context_percent == 25
    assert snapshot.rate_limits[0].used_percent == 40
