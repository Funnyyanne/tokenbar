import json
import os
import sqlite3
import time
from pathlib import Path

from ai_cli_statusline.adapters.claude import ClaudeAdapter
from ai_cli_statusline.adapters.codex import CodexAdapter
from ai_cli_statusline.adapters.kimi import KimiAdapter
from ai_cli_statusline.adapters.cursor import CursorAdapter
from ai_cli_statusline.adapters.opencode import OpenCodeAdapter
from ai_cli_statusline.adapters.generic import GenericCliAdapter
from ai_cli_statusline.adapters.sqlite import SqliteAdapter, SqliteSchema
from ai_cli_statusline.cli import make_adapters
from ai_cli_statusline.render import render_snapshot


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


def test_scanner_keeps_searching_past_fifty_files_without_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path / "cache"))
    valid = tmp_path / "oldest.jsonl"
    write_log(valid)
    os.utime(valid, (100, 100))
    for index in range(50):
        path = tmp_path / f"metadata-{index:02d}.jsonl"
        path.write_text(json.dumps({"event": "session_started"}) + "\n", encoding="utf-8")
        os.utime(path, (200 + index, 200 + index))

    snapshot = ClaudeAdapter([tmp_path]).snapshot()

    assert snapshot.tokens == 182
    assert snapshot.source == str(valid)


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
    schema = SqliteSchema(
        table="requests",
        input_columns=("input_tokens",),
        output_columns=("output_tokens",),
        cache_columns=("cache_read_tokens",),
        model_column="model",
    )
    snapshot = SqliteAdapter("cursor", [tmp_path], schemas=(schema,)).snapshot()
    assert snapshot.tokens == 127
    assert snapshot.input_tokens == 107
    assert snapshot.output_tokens == 20
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 0
    connection.close()


def test_auto_provider_catalog_only_includes_verified_tools():
    adapters = list(make_adapters(["auto"]))
    providers = {adapter.provider for adapter in adapters}
    assert providers == {"codex", "claude", "kimi", "opencode"}


def test_auto_keeps_explicit_additional_provider_without_duplicates():
    adapters = list(make_adapters(["auto", "cursor", "codex"]))
    providers = [adapter.provider for adapter in adapters]
    assert providers == ["codex", "claude", "kimi", "opencode", "cursor"]


def test_sqlite_adapter_does_not_double_count_total_column(tmp_path):
    path = tmp_path / "usage.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE requests (input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER)")
    connection.execute("INSERT INTO requests VALUES (100, 20, 120)")
    connection.commit()
    connection.close()
    schema = SqliteSchema(
        table="requests",
        input_columns=("input_tokens",),
        output_columns=("output_tokens",),
        total_columns=("total_tokens",),
    )
    snapshot = SqliteAdapter("cursor", [tmp_path], schemas=(schema,)).snapshot()
    assert snapshot.tokens == 120


def test_sqlite_adapter_never_queries_credential_columns(tmp_path, monkeypatch):
    path = tmp_path / "provider.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE account (access_token TEXT, refresh_token TEXT, token_expiry INTEGER)")
    connection.execute("INSERT INTO account VALUES ('secret-access', 'secret-refresh', 987654321)")
    connection.commit()
    connection.close()

    statements: list[str] = []
    original_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        traced = original_connect(*args, **kwargs)
        traced.set_trace_callback(statements.append)
        return traced

    monkeypatch.setattr("ai_cli_statusline.adapters.sqlite.sqlite3.connect", traced_connect)
    schema = SqliteSchema(
        table="requests",
        input_columns=("input_tokens",),
        output_columns=("output_tokens",),
    )
    snapshot = SqliteAdapter("demo", [tmp_path], schemas=(schema,)).snapshot()

    assert snapshot.tokens is None
    assert snapshot.error == "未找到可识别 token 字段"
    selected = "\n".join(statement.lower() for statement in statements if statement.lstrip().upper().startswith("SELECT"))
    assert "access_token" not in selected
    assert "refresh_token" not in selected
    assert "token_expiry" not in selected


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


def test_codex_thread_falls_back_when_newest_database_has_no_usage(tmp_path):
    older = tmp_path / "state_1.sqlite"
    connection = sqlite3.connect(older)
    connection.execute("CREATE TABLE threads (tokens_used INTEGER, updated_at INTEGER, updated_at_ms INTEGER, model TEXT, archived INTEGER, thread_source TEXT)")
    connection.execute("INSERT INTO threads VALUES (42, 1, NULL, 'model-ok', 0, 'user')")
    connection.commit()
    connection.close()
    newest = tmp_path / "state_2.sqlite"
    connection = sqlite3.connect(newest)
    connection.execute("CREATE TABLE threads (tokens_used INTEGER, updated_at INTEGER, updated_at_ms INTEGER, model TEXT, archived INTEGER, thread_source TEXT)")
    connection.commit()
    connection.close()
    os.utime(older, (100, 100))
    os.utime(newest, (200, 200))

    assert CodexAdapter(tmp_path)._thread() == (42, 1000, "model-ok")


def test_codex_keeps_local_usage_when_rate_limit_rpc_fails(tmp_path, monkeypatch):
    adapter = CodexAdapter(tmp_path)
    monkeypatch.setattr(adapter, "_thread", lambda: (42, 1000, "model-ok"))

    def fail_rpc(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(adapter, "_rpc", fail_rpc)
    snapshot = adapter.snapshot()

    assert snapshot.tokens == 42
    assert snapshot.error == "额度不可用：offline"
    rendered = render_snapshot(snapshot, color=False)
    assert "total 42" in rendered
    assert "额度不可用：offline" in rendered


def test_jsonl_scanner_counts_complete_file_beyond_tail_limit(tmp_path):
    path = tmp_path / "long.jsonl"
    rows = [json.dumps({"usage": {"input_tokens": 100, "output_tokens": 10}})]
    rows.append(json.dumps({"event": "padding", "value": "x" * (8 * 1024 * 1024)}))
    rows.append(json.dumps({"usage": {"input_tokens": 2, "output_tokens": 1}}))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    snapshot = ClaudeAdapter([tmp_path]).snapshot()

    assert path.stat().st_size > 8 * 1024 * 1024
    assert snapshot.tokens == 113


def test_opencode_reads_only_materialized_session_usage(tmp_path):
    path = tmp_path / "opencode.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE session (id TEXT PRIMARY KEY, tokens_input INTEGER, tokens_output INTEGER, tokens_reasoning INTEGER, tokens_cache_read INTEGER, tokens_cache_write INTEGER)"
    )
    connection.execute("INSERT INTO session VALUES ('s1', 100, 20, 3, 7, 2)")
    connection.execute("CREATE TABLE message (id TEXT PRIMARY KEY, data TEXT)")
    connection.execute("INSERT INTO message VALUES ('m1', ?)", (json.dumps({"prompt": "must-not-be-read", "tokens": {"input": 999}}),))
    connection.execute("CREATE TABLE event (id TEXT PRIMARY KEY, data TEXT)")
    connection.execute("INSERT INTO event VALUES ('e1', ?)", (json.dumps({"tokens": {"input": 999}}),))
    connection.commit()
    connection.close()

    snapshot = OpenCodeAdapter([tmp_path]).snapshot()

    assert snapshot.tokens == 132
    assert snapshot.input_tokens == 109
    assert snapshot.output_tokens == 23
    assert snapshot.maturity == "stable"


def test_opencode_ignores_wrong_schema_and_falls_back(tmp_path):
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    valid = valid_dir / "opencode.db"
    connection = sqlite3.connect(valid)
    connection.execute(
        "CREATE TABLE session (tokens_input INTEGER, tokens_output INTEGER, tokens_reasoning INTEGER, tokens_cache_read INTEGER, tokens_cache_write INTEGER)"
    )
    connection.execute("INSERT INTO session VALUES (4, 3, 2, 1, 0)")
    connection.commit()
    connection.close()
    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    invalid = invalid_dir / "opencode.db"
    connection = sqlite3.connect(invalid)
    connection.execute("CREATE TABLE account (access_token TEXT, token_expiry INTEGER)")
    connection.commit()
    connection.close()
    os.utime(valid, (100, 100))
    os.utime(invalid, (200, 200))

    snapshot = OpenCodeAdapter([tmp_path]).snapshot()

    assert snapshot.tokens == 10
    assert snapshot.source == str(valid)


def test_cursor_adapter_does_not_open_local_credential_database(tmp_path, monkeypatch):
    opened: list[object] = []

    def forbidden_connect(*args, **kwargs):
        opened.append(args)
        raise AssertionError("Cursor adapter must not open credential databases")

    monkeypatch.setattr(sqlite3, "connect", forbidden_connect)
    snapshot = CursorAdapter((tmp_path,)).snapshot()

    assert opened == []
    assert snapshot.tokens is None
    assert snapshot.maturity == "experimental"
    assert "认证 token" in (snapshot.error or "")
