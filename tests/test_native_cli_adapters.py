import json
import sqlite3
from dataclasses import asdict

import pytest

from ai_cli_statusline.adapters import CopilotAdapter, DevinAdapter


def copilot_store(path, rows):
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE assistant_usage_events (
        id INTEGER PRIMARY KEY, session_id TEXT, model TEXT, input_tokens INTEGER,
        output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER,
        reasoning_tokens INTEGER, token_details_json TEXT, created_at TEXT, auth_token TEXT)""")
    for row in rows:
        db.execute("INSERT INTO assistant_usage_events VALUES (?, 'session', 'copilot-test', ?, ?, 40, 10, 5, '[]', '2026-10-03T00:00:00Z', 'CREDENTIAL_SENTINEL')", row)
    db.commit()
    db.close()


def devin_store(path, rows, sessions=True):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE message_nodes (row_id INTEGER, session_id TEXT, chat_message TEXT)")
    if sessions:
        db.execute("CREATE TABLE sessions (id TEXT, created_at INTEGER, cogs_json TEXT)")
        db.execute("INSERT INTO sessions VALUES ('parent', 1, 'PRIVATE_COGS_SENTINEL')")
        db.execute("INSERT INTO sessions VALUES ('fork', 2, 'PRIVATE_COGS_SENTINEL')")
    for row_id, session_id, value in rows:
        db.execute("INSERT INTO message_nodes VALUES (?, ?, ?)", (row_id, session_id, json.dumps(value)))
    db.commit()
    db.close()


def assistant(request_id="request", input_value=100, output_value=20, **metadata):
    return {"role": "assistant", "content": "PRIVATE_REPLY_SENTINEL", "metadata": {
        "request_id": request_id, "generation_model": "swe-test", "started_generation_at": "2026-10-03T00:00:00Z",
        "metrics": {"input_tokens": input_value, "output_tokens": output_value,
            "cache_read_tokens": 4, "cache_creation_tokens": 3}, **metadata}}


def test_copilot_native_store_uses_inclusive_parents_without_double_count(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    path = tmp_path / "session-store.db"
    copilot_store(path, [(1, 100, 20), (2, 10, 2)])
    before = path.read_bytes()
    snapshot = CopilotAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (132, 110, 22)
    assert snapshot.model == "copilot-test"
    assert path.read_bytes() == before
    assert "CREDENTIAL_SENTINEL" not in json.dumps(asdict(snapshot), default=str)


def test_copilot_native_store_takes_priority_over_mirrored_otel(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    copilot_store(tmp_path / "session-store.db", [(1, 100, 20)])
    (tmp_path / "copilot.jsonl").write_text(json.dumps({"spanId": "mirror", "attributes": {
        "gen_ai.operation.name": "chat", "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20}}) + "\n")
    snapshot = CopilotAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 120
    assert snapshot.source.endswith("session-store.db")


def test_copilot_empty_canonical_store_does_not_revive_stale_otel(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    copilot_store(tmp_path / "session-store.db", [])
    (tmp_path / "copilot.jsonl").write_text(json.dumps({"attributes": {
        "gen_ai.operation.name": "chat", "gen_ai.usage.input_tokens": 100,
        "gen_ai.usage.output_tokens": 20}}) + "\n")
    snapshot = CopilotAdapter([tmp_path]).snapshot()
    assert snapshot.tokens is None
    assert snapshot.source.endswith("session-store.db")


def test_copilot_otel_cli_parents_include_both_cache_types_and_reasoning(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    record = {"type": "span", "name": "chat test", "traceId": "trace", "spanId": "span", "attributes": {
        "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20,
        "gen_ai.usage.cache_read.input_tokens": 30, "gen_ai.usage.cache_write.input_tokens": 10,
        "gen_ai.usage.reasoning.output_tokens": 5}}
    corrected = {**record, "attributes": {**record["attributes"], "gen_ai.usage.output_tokens": 25}}
    (tmp_path / "copilot.jsonl").write_text("\n".join(map(json.dumps, [record, record, corrected])) + "\n")
    adapter = CopilotAdapter([tmp_path])
    assert (adapter.snapshot().tokens, adapter.snapshot().input_tokens, adapter.snapshot().output_tokens) == (125, 100, 25)


def test_copilot_chat_responses_share_context_without_losing_usage(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    def record(response_id):
        return {"spanContext": {"spanId": "shared", "traceId": "shared"}, "body": "PRIVATE_REPLY_SENTINEL",
            "attributes": {"gen_ai.operation.name": "chat", "gen_ai.response.id": response_id,
                "gen_ai.usage.input_tokens": {"intValue": "100"}, "gen_ai.usage.output_tokens": 20,
                "gen_ai.usage.cache_creation.input_tokens": 10}}
    (tmp_path / "copilot.jsonl").write_text("\n".join(map(json.dumps, [record("r1"), record("r2"), record("r1")])) + "\n")
    assert CopilotAdapter([tmp_path]).snapshot().tokens == 260


def test_copilot_full_stream_projects_only_allowlisted_metadata(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    path = tmp_path / "copilot.jsonl"
    with path.open("w") as handle:
        handle.write(json.dumps({"type": "span", "attributes": {"gen_ai.operation.name": "chat",
            "gen_ai.usage.input_tokens": 100, "gen_ai.usage.output_tokens": 20}}) + "\n")
        handle.write(json.dumps({"body": "PRIVATE_" + "x" * (8 * 1024 * 1024 + 100)}) + "\n")
        handle.write("broken tail")
    # A full response object must never be decoded in the reader.
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded private object"))
    assert CopilotAdapter([tmp_path]).snapshot().tokens == 120


def test_copilot_does_not_count_metric_envelopes_as_chat_spans(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    (tmp_path / "copilot.jsonl").write_text(json.dumps({"scopeMetrics": [{"name": "metric"}],
        "attributes": {"gen_ai.operation.name": "chat", "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.output_tokens": 20}}) + "\n")
    assert CopilotAdapter([tmp_path]).snapshot().tokens is None


@pytest.mark.parametrize("values", [[(1, None, 20)], [(1, -10, 20)], [(1, 1.5, 20)]])
def test_copilot_native_rejects_incomplete_or_invalid_usage(tmp_path, values):
    copilot_store(tmp_path / "session-store.db", values)
    assert CopilotAdapter([tmp_path]).snapshot().tokens is None


def test_devin_global_request_id_deduplicates_replay_fork_and_compaction(tmp_path):
    path = tmp_path / "sessions.db"
    message = assistant()
    devin_store(path, [(1, "parent", message), (2, "fork", message), (3, "parent", message)])
    before = path.read_bytes()
    snapshot = DevinAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (127, 107, 20)
    assert snapshot.model == "swe-test"
    assert path.read_bytes() == before
    assert "PRIVATE_" not in json.dumps(asdict(snapshot), default=str)


def test_devin_canonical_parent_correction_wins_over_later_fork(tmp_path):
    devin_store(tmp_path / "sessions.db", [
        (1, "parent", assistant(input_value=100)),
        (2, "parent", assistant(input_value=120)),
        (3, "fork", assistant(input_value=999)),
    ])
    assert DevinAdapter([tmp_path]).snapshot().tokens == 147


def test_devin_only_finalized_assistant_metadata_is_counted(tmp_path):
    valid = assistant()
    devin_store(tmp_path / "sessions.db", [
        (1, "parent", valid),
        (2, "parent", {**assistant("user"), "role": "user"}),
        (3, "parent", assistant(None)),
        (4, "parent", assistant("pending", input_value=None)),
        (5, "parent", assistant("negative", input_value=-1)),
        (6, "parent", assistant("boolean", input_value=True)),
        (7, "parent", assistant("bad-time", started_generation_at="invalid", created_at="invalid")),
    ])
    assert DevinAdapter([tmp_path]).snapshot().tokens == 127


def test_devin_optional_sessions_table_and_original_created_time(tmp_path):
    message = assistant(started_generation_at=None, created_at="2026-10-03T00:00:00Z")
    devin_store(tmp_path / "sessions.db", [(1, "parent", message)], sessions=False)
    adapter = DevinAdapter([tmp_path])
    assert adapter.snapshot().tokens == adapter.snapshot().tokens == 127


def test_devin_nested_model_object_never_leaves_sqlite(tmp_path):
    devin_store(tmp_path / "sessions.db", [(1, "parent", assistant(generation_model={"content": "PRIVATE_MODEL_SENTINEL"}))])
    snapshot = DevinAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 127
    assert snapshot.model is None


def test_native_readers_never_select_private_database_columns(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    copilot_store(tmp_path / "session-store.db", [(1, 100, 20)])
    devin_store(tmp_path / "sessions.db", [(1, "parent", assistant())])
    connect = sqlite3.connect
    def guarded(*args, **kwargs):
        connection = connect(*args, **kwargs)
        def authorize(action, _table, column, _database, _trigger):
            if action == sqlite3.SQLITE_READ and column in {"auth_token", "token_details_json", "cogs_json"}:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        connection.set_authorizer(authorize)
        return connection
    monkeypatch.setattr(sqlite3, "connect", guarded)
    assert CopilotAdapter([tmp_path]).snapshot().tokens == 120
    assert DevinAdapter([tmp_path]).snapshot().tokens == 127


@pytest.mark.parametrize("value", [-1, True, "bad", 1.5])
def test_devin_invalid_cache_metrics_do_not_become_zero(tmp_path, value):
    message = assistant()
    message["metadata"]["metrics"]["cache_creation_tokens"] = value
    devin_store(tmp_path / "sessions.db", [(1, "parent", message)])
    assert DevinAdapter([tmp_path]).snapshot().tokens is None


def test_native_readers_handle_reserved_uri_paths_and_corrupt_files(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    root = tmp_path / "space # question?"
    root.mkdir()
    copilot_store(root / "session-store.db", [(1, 10, 2)])
    devin_store(root / "sessions.db", [(1, "parent", assistant())])
    assert CopilotAdapter([root]).snapshot().tokens == 12
    assert DevinAdapter([root]).snapshot().tokens == 127
    invalid = tmp_path / "corrupt"
    invalid.mkdir()
    (invalid / "sessions.db").write_text("not sqlite")
    assert DevinAdapter([invalid]).snapshot().tokens is None
