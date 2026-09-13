import json
from pathlib import Path

from ai_cli_statusline.adapters.claude import ClaudeAdapter
from ai_cli_statusline.adapters.kimi import KimiAdapter


def write_log(path: Path):
    path.write_text(
        "\n".join(
            [
                json.dumps({"message": {"model": "claude-sonnet", "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 7}}}),
                json.dumps({"model": "claude-sonnet", "usage": {"input_tokens": 50, "output_tokens": 5}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_claude_scanner_sums_nested_usage(tmp_path):
    path = tmp_path / "session.jsonl"
    write_log(path)
    snapshot = ClaudeAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 182
    assert snapshot.input_tokens == 157
    assert snapshot.output_tokens == 25
    assert snapshot.model == "claude-sonnet"


def test_kimi_scanner_is_configurable(tmp_path):
    path = tmp_path / "kimi.jsonl"
    write_log(path)
    snapshot = KimiAdapter([tmp_path]).snapshot()
    assert snapshot.provider == "kimi"
    assert snapshot.tokens == 182
