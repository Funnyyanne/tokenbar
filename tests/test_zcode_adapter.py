import json
import sqlite3

import pytest

from ai_cli_statusline.adapters import ZCodeAdapter


def database(path, native=None, legacy=None):
    db = sqlite3.connect(path)
    if native is not None:
        db.execute("""CREATE TABLE model_usage (id TEXT, logical_request_id TEXT, attempt_index INTEGER,
            session_id TEXT, provider_id TEXT, model_id TEXT, status TEXT, started_at INTEGER,
            input_tokens INTEGER, output_tokens INTEGER, reasoning_tokens INTEGER,
            cache_creation_input_tokens INTEGER, cache_read_input_tokens INTEGER, auth_token TEXT)""")
        for identity, provider, status, started, input_value, output_value in native:
            db.execute("INSERT INTO model_usage VALUES (?, ?, 0, 'session', ?, 'custom-model', ?, ?, ?, ?, 5, 10, 30, 'CREDENTIAL_SENTINEL')",
                (identity, identity, provider, status, started, input_value, output_value))
    if legacy is not None:
        db.execute("CREATE TABLE message (id TEXT, time_updated INTEGER, data TEXT)")
        for identity, provider, time, input_value, output_value in legacy:
            message = {"role": "assistant", "model": {"providerID": provider, "modelID": "legacy-model"},
                "tokens": {"input": input_value, "output": output_value, "reasoning": 5, "cache": {"read": 30, "write": 10}},
                "content": "PRIVATE_REPLY_SENTINEL"}
            db.execute("INSERT INTO message VALUES (?, ?, ?)", (identity, time, json.dumps(message)))
    db.commit()
    db.close()


def test_zcode_legacy_inclusive_parents_and_custom_provider_filter(tmp_path):
    database(tmp_path / "db.sqlite", legacy=[
        ("custom", "265956bf-custom", 1000, 100, 20),
        ("builtin", "builtin:zai-start-plan", 1000, 100, 20),
        ("claude", "anthropic", 1000, 100, 20),
        ("codex", "openai", 1000, 100, 20),
        ("gemini", "builtin:google", 1000, 100, 20),
        ("unknown", None, 1000, 100, 20),
    ])
    snapshot = ZCodeAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (240, 200, 40)
    assert snapshot.model == "legacy-model"


def test_zcode_native_requires_completed_and_excludes_mirrored_subagents(tmp_path):
    database(tmp_path / "db.sqlite", native=[
        ("completed", "custom-uuid", "completed", 2000, 100, 20),
        ("failed", "custom-uuid", "failed", 2000, 100, 20),
        ("pending", "custom-uuid", "started", 2000, 100, 20),
        ("mirror", "anthropic", "completed", 2000, 100, 20),
        ("invalid", "custom-uuid", "completed", 2000, -100, 20),
    ])
    assert ZCodeAdapter([tmp_path]).snapshot().tokens == 120


def test_zcode_transition_keeps_old_history_without_readding_native_mirror(tmp_path):
    path = tmp_path / "db.sqlite"
    database(path, native=[("n1", "custom", "completed", 2000, 100, 20)], legacy=[
        ("older", "custom", 1000, 100, 20),
        ("same", "custom", 2000, 100, 20),
        ("newer", "custom", 3000, 100, 20),
    ])
    before = path.read_bytes()
    adapter = ZCodeAdapter([tmp_path])
    assert adapter.snapshot().tokens == adapter.snapshot().tokens == 240
    assert path.read_bytes() == before


def test_zcode_empty_native_table_does_not_hide_legacy_history(tmp_path):
    database(tmp_path / "db.sqlite", native=[], legacy=[("old", "custom", 1000, 100, 20)])
    assert ZCodeAdapter([tmp_path]).snapshot().tokens == 120


@pytest.mark.parametrize("input_value,output_value,provider_total,computed_total,expected", [
    (0, 0, 45, 45, (45, 40, 5)),
    (None, None, None, None, (45, 40, 5)),
    (0, 20, None, None, (60, 40, 20)),
    (100, 0, None, None, (105, 100, 5)),
    (100, 20, None, None, (120, 100, 20)),
    (100, 20, 150, 170, (150, 100, 20)),
    (100, 20, 0, 170, (170, 100, 20)),
    (100, 20, -1, 170, (170, 100, 20)),
    (100, 20, 1.5, None, (120, 100, 20)),
])
def test_zcode_native_preserves_explicit_totals_and_missing_parent_fallbacks(
    tmp_path, monkeypatch, input_value, output_value, provider_total, computed_total, expected,
):
    path = tmp_path / "db.sqlite"
    database(path, native=[("completed", "custom", "completed", 2000, input_value, output_value)])
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE model_usage ADD COLUMN provider_total_tokens INTEGER")
        db.execute("ALTER TABLE model_usage ADD COLUMN computed_total_tokens INTEGER")
        db.execute("UPDATE model_usage SET provider_total_tokens = ?, computed_total_tokens = ?",
            (provider_total, computed_total))
    before = path.read_bytes()
    connect = sqlite3.connect
    def guarded(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.set_authorizer(lambda action, _table, column, _database, _trigger:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and column == "auth_token" else sqlite3.SQLITE_OK)
        return db
    monkeypatch.setattr(sqlite3, "connect", guarded)
    reader = ZCodeAdapter([tmp_path])
    snapshot = reader.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == expected
    assert reader.snapshot().tokens == expected[0]
    assert path.read_bytes() == before


def test_zcode_total_only_record_does_not_invent_input_output_split(tmp_path):
    path = tmp_path / "db.sqlite"
    database(path, native=[("completed", "custom", "completed", 2000, None, None)])
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE model_usage ADD COLUMN provider_total_tokens INTEGER")
        db.execute("UPDATE model_usage SET provider_total_tokens = 45, reasoning_tokens = NULL, "
            "cache_creation_input_tokens = NULL, cache_read_input_tokens = NULL")
    snapshot = ZCodeAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (45, 0, 0)
