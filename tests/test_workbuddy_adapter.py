import json
import os
import sqlite3
from dataclasses import asdict

import pytest

from ai_cli_statusline.adapters import WorkBuddyAdapter
from ai_cli_statusline.cli import make_adapters


def detail(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(map(json.dumps, records)) + "\n")


def response(identity="response", session="session", input_value=100, output_value=20):
    return {"sessionId": session, "type": "function_call", "providerData": {
        "messageId": identity, "model": "hy3", "rawUsage": {
            "prompt_tokens": input_value, "completion_tokens": output_value,
            "cache_read_input_tokens": 30, "cache_creation_input_tokens": 10}},
        "content": "PRIVATE_REPLY_SENTINEL"}


def trace(path, session="session", *, nested=False, **changes):
    info = {"models": ["hy3"], "totalInputTokens": 1000, "totalOutputTokens": 200,
        "totalCachedTokens": 600, **changes}
    metadata = {"sessionId": session, "startedAt": "2026-10-03T00:00:00Z", "modelInfo": info}
    record = {"trace": {"traceId": "trace-" + session, **({"metadata": metadata} if nested else metadata),
        "events": [{"text": "PRIVATE_REPLY_SENTINEL", "usage": {"input_tokens": 999999}}]},
        "auth_token": "CREDENTIAL_SENTINEL"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))
    return path


def test_workbuddy_main_and_nested_subagents_are_one_session(tmp_path):
    main = tmp_path / "projects" / "workspace" / "session.jsonl"
    child = main.with_suffix("") / "subagents" / "nested" / "agent-child.jsonl"
    detail(main, [response(), response("main-only", input_value=5, output_value=1)])
    detail(child, [response(), response("child", input_value=10, output_value=2)])
    before = main.read_bytes(), child.read_bytes()
    reader = WorkBuddyAdapter([tmp_path])
    snapshot = reader.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (138, 115, 23)
    assert reader.snapshot().tokens == 138
    assert (main.read_bytes(), child.read_bytes()) == before
    assert "PRIVATE_" not in json.dumps(asdict(snapshot), default=str)


def test_workbuddy_cross_file_correction_and_old_session_isolation(tmp_path):
    main = tmp_path / "session.jsonl"
    child = tmp_path / "session" / "subagents" / "agent-child.jsonl"
    old = tmp_path / "old.jsonl"
    detail(old, [response("old", "old", 9999, 9999)])
    detail(main, [response(), response("main-only", input_value=5, output_value=1)])
    detail(child, [response(output_value=25), response("child", input_value=10, output_value=2)])
    for path, modified in ((old, 1000), (main, 2000), (child, 3000)):
        os.utime(path, (modified, modified))
    assert WorkBuddyAdapter([tmp_path]).snapshot().tokens == 143


@pytest.mark.parametrize("nested", [False, True])
def test_workbuddy_trace_explicit_totals_do_not_add_cache_or_decode_body(tmp_path, monkeypatch, nested):
    path = trace(tmp_path / "traces" / "1234" / "trace_only.json", nested=nested)
    before = path.read_bytes()
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded private body"))
    reader = WorkBuddyAdapter([tmp_path])
    snapshot = reader.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (1200, 1000, 200)
    assert snapshot.model == "hy3" and snapshot.maturity == "experimental"
    assert reader.snapshot().tokens == 1200
    assert path.read_bytes() == before
    assert "PRIVATE_" not in str(asdict(snapshot)) and "CREDENTIAL_" not in str(asdict(snapshot))


def test_workbuddy_detailed_session_wins_over_newer_partial_trace(tmp_path):
    main = tmp_path / "projects" / "workspace" / "filename.jsonl"
    detail(main, [response()])
    trace(tmp_path / "traces" / "trace_partial.json")
    assert WorkBuddyAdapter([tmp_path]).snapshot().tokens == 120


def test_workbuddy_rewritten_zero_usage_does_not_restore_stale_trace(tmp_path):
    main = tmp_path / "session.jsonl"
    detail(main, [response(), response(input_value=0, output_value=0)])
    trace(tmp_path / "trace_old.json")
    assert WorkBuddyAdapter([tmp_path]).snapshot().tokens is None


def test_workbuddy_multiple_traces_in_same_session_are_replaced_not_added(tmp_path):
    older = trace(tmp_path / "trace_old.json")
    newer = trace(tmp_path / "trace_new.json", totalInputTokens=1100, totalOutputTokens=250)
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))
    assert WorkBuddyAdapter([tmp_path]).snapshot().tokens == 1350


@pytest.mark.parametrize("changes", [{"totalInputTokens": -1}, {"totalOutputTokens": True},
    {"totalInputTokens": 1.5}, {"totalInputTokens": None}, {"totalInputTokens": 0, "totalOutputTokens": 0}])
def test_workbuddy_invalid_trace_counts_are_unavailable(tmp_path, changes):
    trace(tmp_path / "trace_invalid.json", **changes)
    assert WorkBuddyAdapter([tmp_path]).snapshot().tokens is None


def test_workbuddy_invalid_time_and_unrelated_json_are_unavailable(tmp_path):
    path = trace(tmp_path / "trace_bad.json")
    record = json.loads(path.read_text())
    record["trace"]["startedAt"] = "bad"
    path.write_text(json.dumps(record))
    trace(tmp_path / "settings.json")
    assert WorkBuddyAdapter([tmp_path]).snapshot().tokens is None


def test_workbuddy_context_and_credits_database_is_not_opened(tmp_path, monkeypatch):
    with sqlite3.connect(tmp_path / "workbuddy.db") as db:
        db.execute("CREATE TABLE session_usage (used INTEGER, size INTEGER, credit_json TEXT, auth_token TEXT)")
        db.execute("INSERT INTO session_usage VALUES (90000, 100000, '9999', 'CREDENTIAL_SENTINEL')")
    monkeypatch.setattr(sqlite3, "connect", lambda *_args, **_kwargs: pytest.fail("opened context/auth database"))
    assert WorkBuddyAdapter([tmp_path]).snapshot().tokens is None


def test_workbuddy_home_and_custom_roots_keep_dedicated_parser(tmp_path, monkeypatch):
    trace(tmp_path / "home" / "traces" / "trace_home.json")
    monkeypatch.setenv("WORKBUDDY_HOME", str(tmp_path / "home"))
    assert WorkBuddyAdapter().snapshot().tokens == 1200
    trace(tmp_path / "custom" / "trace_custom.json", totalInputTokens=100, totalOutputTokens=20)
    monkeypatch.setenv("AI_CLI_STATUSLINE_SOURCES", json.dumps({"workbuddy": [str(tmp_path / "custom")]}))
    assert next(make_adapters(["workbuddy"])).snapshot().tokens == 120
