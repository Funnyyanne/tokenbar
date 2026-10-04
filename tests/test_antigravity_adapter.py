import json
import sqlite3
from dataclasses import asdict

import pytest

from ai_cli_statusline.cli import make_adapters


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def number(field, value):
    return varint(field << 3) + varint(value)


def blob(field, value):
    if isinstance(value, str):
        value = value.encode()
    return varint((field << 3) | 2) + varint(len(value)) + value


def generation(step=0, *, usage=None, context=25000, unknown=b""):
    body = blob(19, "gemini-test")
    body += blob(9, number(2, 2**64 - 1) + blob(10, number(1, context)))
    body += blob(20, blob(1, "last_step_index") + blob(2, str(step)))
    if usage is not None:
        body += blob(4, b"".join(number(field, count) for field, count in usage.items()))
    body += blob(99, "PRIVATE_REPLY_SENTINEL") + unknown
    return blob(1, body)


def fixture(root, entries, planner_steps=(1,), *, wal=False):
    directory = root / "antigravity-cli" / "conversations"
    directory.mkdir(parents=True)
    path = directory / "conversation.db"
    db = sqlite3.connect(path)
    if wal:
        db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE gen_metadata (idx INTEGER PRIMARY KEY, data BLOB)")
    db.execute("CREATE TABLE messages (content TEXT, auth_token TEXT)")
    db.execute("INSERT INTO messages VALUES ('PRIVATE_REPLY_SENTINEL','CREDENTIAL_SENTINEL')")
    for index, entry in enumerate(entries):
        db.execute("INSERT INTO gen_metadata VALUES (?, ?)", (index, entry))
    db.commit()
    logs = root / "antigravity-cli" / "brain" / "conversation" / ".system_generated" / "logs"
    logs.mkdir(parents=True)
    records = [{"type": "USER_INPUT", "step_index": 0, "content": "PRIVATE_PROMPT_SENTINEL",
        "usage": {"input_tokens": 999999}}, *[{"type": "PLANNER_RESPONSE", "step_index": step,
            "created_at": "2026-10-03T00:00:00Z", "content": "PRIVATE_REPLY_SENTINEL"} for step in planner_steps]]
    (logs / "transcript.jsonl").write_text("\n".join(map(json.dumps, records)) + "\n")
    if not wal:
        db.close()
    return path, db if wal else None


def adapter(root, monkeypatch):
    monkeypatch.setenv("AI_CLI_STATUSLINE_SOURCES", json.dumps({"antigravity": [str(root / "antigravity-cli")]}))
    return next(make_adapters(["antigravity"]))


def test_antigravity_explicit_metadata_includes_prefix_cache_text_and_reasoning(tmp_path, monkeypatch):
    path, _ = fixture(tmp_path, [generation(usage={1: 10, 2: 100, 3: 50, 5: 30, 9: 40, 10: 10})])
    before = path.read_bytes()
    snapshot = adapter(tmp_path, monkeypatch).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (190, 140, 50)
    assert snapshot.model == "gemini-test"
    assert snapshot.context_used == 25000
    assert snapshot.context_window is None
    assert snapshot.maturity == "experimental"
    assert path.read_bytes() == before
    assert "PRIVATE_" not in json.dumps(asdict(snapshot), default=str)


def test_antigravity_same_step_correction_replaces_earlier_generation(tmp_path, monkeypatch):
    fixture(tmp_path, [generation(usage={2: 100, 3: 20}), generation(usage={2: 120, 3: 25}),
        generation(2, usage={2: 10, 3: 2})], planner_steps=(1, 1, 3))
    reader = adapter(tmp_path, monkeypatch)
    assert reader.snapshot().tokens == reader.snapshot().tokens == 157


def test_antigravity_checksum_is_fallback_and_never_added_to_text_and_reasoning(tmp_path, monkeypatch):
    fixture(tmp_path, [generation(usage={2: 100, 3: 500, 9: 40, 10: 10}),
        generation(2, usage={2: 100, 3: 50, 10: 10})], planner_steps=(1, 3))
    assert adapter(tmp_path, monkeypatch).snapshot().tokens == 300


def test_antigravity_no_planner_response_means_generation_is_not_finalized(tmp_path, monkeypatch):
    fixture(tmp_path, [generation(usage={2: 100, 3: 20})], planner_steps=())
    assert adapter(tmp_path, monkeypatch).snapshot().tokens is None


def test_antigravity_context_only_metadata_does_not_become_billed_tokens(tmp_path, monkeypatch):
    fixture(tmp_path, [generation()])
    assert adapter(tmp_path, monkeypatch).snapshot().tokens is None


@pytest.mark.parametrize("payload", [b"\x0a\x80\x80", b"\x0a\x05\x08", blob(1, b"\x00"),
    blob(1, b"\x08" + b"\xff" * 9 + b"\x02")])
def test_antigravity_truncated_invalid_or_overflow_proto_is_unavailable(tmp_path, monkeypatch, payload):
    fixture(tmp_path, [payload])
    assert adapter(tmp_path, monkeypatch).snapshot().tokens is None


def test_antigravity_unsafe_token_varint_is_ignored_without_rejecting_valid_metadata(tmp_path, monkeypatch):
    fixture(tmp_path, [generation(usage={2: 2**64 - 1, 5: 30, 3: 20})])
    assert adapter(tmp_path, monkeypatch).snapshot().tokens == 50


def test_antigravity_reads_active_wal_and_never_queries_message_or_auth_table(tmp_path, monkeypatch):
    path, writer = fixture(tmp_path, [generation(usage={2: 100, 3: 20})], wal=True)
    connect = sqlite3.connect
    def guarded(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.set_authorizer(lambda action, table, _column, _database, _trigger:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "messages" else sqlite3.SQLITE_OK)
        return db
    monkeypatch.setattr(sqlite3, "connect", guarded)
    try:
        before = path.read_bytes(), path.with_name(path.name + "-wal").read_bytes()
        assert adapter(tmp_path, monkeypatch).snapshot().tokens == 120
        assert (path.read_bytes(), path.with_name(path.name + "-wal").read_bytes()) == before
    finally:
        writer.close()
