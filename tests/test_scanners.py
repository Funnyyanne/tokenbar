import json
import os
import sqlite3
import time
from pathlib import Path

from ai_cli_statusline.adapters.claude import ClaudeAdapter
from ai_cli_statusline.adapters.codex import CodexAdapter
from ai_cli_statusline.adapters.kimi import KimiAdapter
from ai_cli_statusline.adapters.generic import GenericCliAdapter
from ai_cli_statusline.adapters.sqlite import SqliteAdapter
from ai_cli_statusline.cli import make_adapters


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


def test_scanner_skips_newest_file_without_usage(tmp_path):
    valid = tmp_path / "older.jsonl"
    write_log(valid)
    empty = tmp_path / "newer.jsonl"
    empty.write_text(json.dumps({"event": "session_started"}) + "\n", encoding="utf-8")
    os.utime(empty, (time.time() + 10, time.time() + 10))
    snapshot = ClaudeAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 182


def test_kimi_wire_jsonl_prompt_completion_aliases(tmp_path):
    path = tmp_path / "wire.jsonl"
    path.write_text(
        json.dumps({"event": "turn.finished", "usage": {"prompt_tokens": 12, "completion_tokens": 4, "cacheReadTokens": 2}}) + "\n",
        encoding="utf-8",
    )
    snapshot = KimiAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 18
    assert snapshot.input_tokens == 14
    assert snapshot.output_tokens == 4


def test_kimi_wire_jsonl_native_usage_fields(tmp_path):
    path = tmp_path / "wire.jsonl"
    path.write_text(
        json.dumps({
            "type": "usage.record",
            "model": "kimi-code/k3",
            "usage": {
                "inputOther": 2704,
                "output": 74,
                "inputCacheRead": 19456,
                "inputCacheCreation": 0,
            },
        }) + "\n",
        encoding="utf-8",
    )
    snapshot = KimiAdapter([tmp_path]).snapshot()
    assert snapshot.model == "kimi-code/k3"
    assert snapshot.tokens == 22234
    assert snapshot.input_tokens == 22160
    assert snapshot.output_tokens == 74


def test_generic_cli_adapter_supports_other_jsonl_tools(tmp_path):
    path = tmp_path / "session.jsonl"
    write_log(path)
    snapshot = GenericCliAdapter("gemini", [tmp_path]).snapshot()
    assert snapshot.provider == "gemini"
    assert snapshot.tokens == 182


def test_sqlite_adapter_reads_usage_columns_read_only(tmp_path):
    path = tmp_path / "usage.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE requests (model TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER)")
    connection.execute("INSERT INTO requests VALUES ('model-x', 100, 20, 7)")
    connection.commit()
    connection.close()
    snapshot = SqliteAdapter("cursor", [tmp_path]).snapshot()
    assert snapshot.tokens == 127
    assert snapshot.input_tokens == 107
    assert snapshot.output_tokens == 20
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 0
    connection.close()


def test_auto_provider_catalog_includes_jsonl_and_sqlite_tools():
    adapters = list(make_adapters(["auto"]))
    providers = {adapter.provider for adapter in adapters}
    assert {"codex", "claude", "kimi", "gemini", "cursor", "opencode"}.issubset(providers)


def test_sqlite_adapter_does_not_double_count_total_column(tmp_path):
    path = tmp_path / "usage.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE requests (input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER)")
    connection.execute("INSERT INTO requests VALUES (100, 20, 120)")
    connection.commit()
    connection.close()
    snapshot = SqliteAdapter("cursor", [tmp_path]).snapshot()
    assert snapshot.tokens == 120


def test_newest_files_survives_missing_files(tmp_path, monkeypatch):
    from ai_cli_statusline.adapters.common import newest_files

    path = tmp_path / "a.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    original_stat = Path.stat

    def flaky_stat(self, *args, **kwargs):
        if self.name == "ghost.jsonl":
            raise OSError("vanished")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)
    (tmp_path / "ghost.jsonl").write_text("{}\n", encoding="utf-8")
    files = newest_files([tmp_path])
    assert path in files


def test_codex_thread_uses_newest_state_database_by_mtime(tmp_path):
    def make_state(path: Path, tokens: int) -> None:
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE threads (tokens_used INTEGER, updated_at INTEGER, updated_at_ms INTEGER, model TEXT, archived INTEGER, thread_source TEXT)")
        connection.execute("INSERT INTO threads VALUES (?, 1, NULL, 'model', 0, 'user')", (tokens,))
        connection.commit()
        connection.close()

    older = tmp_path / "state_10.sqlite"
    newer = tmp_path / "state_9.sqlite"
    make_state(older, 10)
    make_state(newer, 20)
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))
    tokens, _updated, _model = CodexAdapter(tmp_path)._thread()
    assert tokens == 20
