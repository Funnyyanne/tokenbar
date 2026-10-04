import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest

from ai_cli_statusline.adapters import (
    CodeBuddyAdapter, CommandCodeAdapter, DotsAdapter, MiniMaxAdapter,
    MimoAdapter, OmoAdapter, PiAdapter, PrimeAdapter, ReasonixAdapter, WorkBuddyAdapter,
    ClaudeScienceAdapter, DroidAdapter, HermesAdapter, OpenClawAdapter,
    AStudioAdapter, ClineAdapter, EveryCodeAdapter, KiloAdapter, QoderAdapter, QoderCNAdapter,
)
from ai_cli_statusline.adapters.metadata import json_metadata, token_count
from ai_cli_statusline.cli import collect, make_adapters
from ai_cli_statusline.providers import PROVIDER_SPECS, auto_provider_names


def write_lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(map(json.dumps, values)) + "\n")


@pytest.mark.parametrize("adapter", [CodeBuddyAdapter, WorkBuddyAdapter])
def test_buddy_response_ids_include_function_calls_without_double_count(tmp_path, adapter):
    rows = [
        {"type": "function_call", "id": "append-1", "providerData": {
            "messageId": "response-1", "model": "hy3", "rawUsage": {
                "prompt_tokens": 100, "completion_tokens": 20,
                "cache_read_input_tokens": 40, "cache_creation_input_tokens": 10,
                "completion_tokens_details": {"reasoning_tokens": 5},
            }}},
        {"type": "assistant", "id": "append-2", "providerData": {
            "messageId": "response-1", "model": "hy3", "rawUsage": {
                "prompt_tokens": 100, "completion_tokens": 20}}},
        {"id": "append-3", "providerData": {"messageId": "response-2", "rawUsage": {
            "prompt_tokens": 7, "completion_tokens": 3}}},
        {"type": "user", "content": {"usage": {"prompt_tokens": 9999}}},
    ]
    write_lines(tmp_path / "session.jsonl", rows)
    snapshot = adapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (130, 107, 23)
    assert snapshot.model == "hy3"


@pytest.mark.parametrize("adapter", [OmoAdapter, PrimeAdapter, PiAdapter])
def test_pi_family_ignores_content_and_deduplicates_rewritten_usage(tmp_path, adapter):
    record = {"type": "message", "id": "a", "message": {
        "role": "assistant", "model": "test", "usage": {"input": 10, "output": 4, "cacheRead": 2, "cacheWrite": 1}}}
    correction = {**record, "message": {**record["message"], "usage": {
        "input": 10, "output": 6, "cacheRead": 2, "cacheWrite": 1}}}
    write_lines(tmp_path / "session.jsonl", [record, record, correction, {
        "type": "message", "message": {"role": "user", "usage": {"input": 999},
        "content": {"role": "assistant", "usage": {"input": 999}}}}])
    snapshot = adapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (19, 13, 6)


@pytest.mark.parametrize("backend", ["dots", " Dots "])
def test_omo_reasoning_is_output_subset_and_dots_is_partitioned(tmp_path, backend):
    write_lines(tmp_path / "session.jsonl", [
        {"type": "message", "id": "a", "message": {"role": "assistant", "provider": backend, "usage": {
            "input": 10, "output": 6, "reasoning": 4}}},
        {"type": "message", "id": "b", "message": {"role": "assistant", "provider": "anthropic", "usage": {
            "input": 2, "output": 3}}},
    ])
    assert OmoAdapter([tmp_path]).snapshot().tokens == 21
    assert DotsAdapter([tmp_path]).snapshot().tokens == 16
    assert PiAdapter([tmp_path]).snapshot().tokens == 5


def test_minimax_message_id_and_exact_filename(tmp_path):
    row = {"message_id": "m-1", "message": {"role": "assistant", "model": "MiniMax-M2.7", "usage": {
        "input": 100, "output": 20, "cacheRead": 30, "cacheWrite": 4, "totalTokens": 154, "cost": {"total": 0}}}}
    write_lines(tmp_path / "2026/10/03/session/messages.jsonl", [row, row, {
        "message_id": "legacy", "message": {"role": "assistant", "usage": {"input": 0, "output": 0}}}])
    write_lines(tmp_path / "task-1.readable.v1.jsonl", [{**row, "message_id": "subagent"}])
    snapshot = MiniMaxAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (154, 134, 20)


def test_commandcode_excludes_sidecars_and_replaces_corrected_counters(tmp_path):
    row = {"type": "message", "id": "a", "model": "deepseek/test", "usage": {
        "inputTokens": 100, "outputTokens": 20, "cacheReadTokens": 40, "cacheWriteTokens": 10}}
    write_lines(tmp_path / "session.jsonl", [row, row])
    write_lines(tmp_path / "session.checkpoints.jsonl", [{**row, "id": "checkpoint"}])
    write_lines(tmp_path / "session.prompts.copy.jsonl", [{**row, "id": "prompt"}])
    snapshot = CommandCodeAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (120, 100, 20)
    write_lines(tmp_path / "session.jsonl", [row, {**row, "usage": {"inputTokens": 0, "outputTokens": 0}}])
    assert CommandCodeAdapter([tmp_path]).snapshot().tokens is None


def test_reasonix_telemetry_is_cumulative_and_cache_reasoning_inclusive(tmp_path):
    telemetry = tmp_path / "session.jsonl.telemetry.json"
    telemetry.write_text(json.dumps({"usage": {"promptTokens": 100, "completionTokens": 20,
        "cacheHitTokens": 40, "cacheMissTokens": 60, "cacheWriteTokens": 10, "reasoningTokens": 5}}))
    (tmp_path / "session.jsonl.meta").write_text(json.dumps({"model": "deepseek/test"}))
    # A transcript containing usage-looking body text must never be opened.
    (tmp_path / "session.jsonl").write_text("private content")
    adapter = ReasonixAdapter([tmp_path])
    assert adapter.snapshot().tokens == 120
    assert adapter.snapshot().tokens == 120
    assert adapter.snapshot().model == "deepseek/test"


def test_mimo_ignores_mirrored_history_and_session_aggregates(tmp_path):
    path = tmp_path / "mimocode.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE message (data TEXT)")
    db.execute("CREATE TABLE session (tokens_input INTEGER)")
    db.execute("INSERT INTO session VALUES (9999)")
    for provider, tokens, nested in [("mimo", 10, False), ("xiaomi", 20, True), ("anthropic", 9999, False), ("", 9999, False)]:
        row = {"role": "assistant", "tokens": {"input": tokens, "output": 2}, "content": "PRIVATE_BODY_SENTINEL"}
        row["model" if nested else "providerID"] = {"providerID": provider} if nested else provider
        db.execute("INSERT INTO message VALUES (?)", (json.dumps(row),))
    db.commit()
    db.close()
    before = path.read_bytes()
    snapshot = MimoAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 34
    assert path.read_bytes() == before
    assert "PRIVATE_BODY_SENTINEL" not in json.dumps(asdict(snapshot), default=str)


def test_json_metadata_never_decodes_bodies_in_python(tmp_path, monkeypatch):
    path = tmp_path / "session.jsonl"
    write_lines(path, [{"message": {"role": "assistant", "usage": {"input": 12},
        "content": [{"text": "private prompt/response"}]}, "auth": "private credential"}])
    monkeypatch.setattr(json, "loads", lambda *args, **kwargs: pytest.fail("body was decoded"))
    assert list(json_metadata(path, {"input": "$.message.usage.input"})) == [{"input": 12}]


def test_metadata_excludes_boolean_and_object_token_values(tmp_path):
    write_lines(tmp_path / "session.jsonl", [
        {"type": "message", "id": "a", "message": {"role": "assistant", "usage": {"input": True, "output": {"text": "private"}}}},
    ])
    assert PiAdapter([tmp_path]).snapshot().tokens is None


def test_metadata_full_scan_recovers_after_malformed_and_long_rows(tmp_path):
    path = tmp_path / "session.jsonl"
    write_lines(path, [{"type": "message", "id": "first", "message": {"role": "assistant", "usage": {"input": 10}}},
        {"type": "user", "content": "x" * (8 * 1024 * 1024 + 20)}])
    with path.open("a") as handle:
        handle.write('\nnot json\n[1]\nnull\n{"torn":\n')
        handle.write(json.dumps({"type": "message", "id": "last", "message": {"role": "assistant", "usage": {"output": 2}}}) + "\n")
    assert PiAdapter([tmp_path]).snapshot().tokens == 12


@pytest.mark.parametrize("value", [-1, True, False, 1.5, float("nan"), float("inf"), "cost", None])
def test_invalid_token_counts_are_zero(value):
    assert token_count(value) == 0


@pytest.mark.parametrize("adapter", [CodeBuddyAdapter, WorkBuddyAdapter, OmoAdapter, DotsAdapter, PrimeAdapter,
    MiniMaxAdapter, CommandCodeAdapter, ReasonixAdapter, MimoAdapter,
    ClaudeScienceAdapter, ClineAdapter, DroidAdapter, HermesAdapter, OpenClawAdapter,
    AStudioAdapter, EveryCodeAdapter, QoderAdapter, QoderCNAdapter])
def test_new_reader_empty_or_wrong_format_is_unavailable(tmp_path, adapter):
    (tmp_path / "session.jsonl").write_text('{"usage":{"input_tokens":9999},"auth":"secret"}\n')
    snapshot = adapter([tmp_path]).snapshot()
    assert snapshot.tokens is None and snapshot.error and snapshot.maturity == "experimental"


def test_registered_reader_keeps_dedicated_format_with_custom_roots(tmp_path, monkeypatch):
    write_lines(tmp_path / "session.jsonl", [{"type": "message", "id": "a", "usage": {"inputTokens": 10, "outputTokens": 3}}])
    monkeypatch.setenv("AI_CLI_STATUSLINE_SOURCES", json.dumps({"commandcode": [str(tmp_path)], "minimax": [str(tmp_path)]}))
    adapters = list(make_adapters(["commandcode", "minimax"]))
    assert isinstance(adapters[0], CommandCodeAdapter)
    snapshots = collect(["commandcode", "minimax"])
    assert snapshots[0].tokens == 13
    assert snapshots[1].tokens is None and snapshots[1].error


def test_newest_empty_session_falls_back_and_next_poll_rebuilds(tmp_path):
    older = tmp_path / "older.jsonl"
    newer = tmp_path / "newer.jsonl"
    write_lines(older, [{"type": "message", "id": "a", "usage": {"inputTokens": 10}}])
    newer.write_text("{}\n")
    os.utime(older, (1, 1))
    adapter = CommandCodeAdapter([tmp_path])
    assert adapter.snapshot().tokens == 10
    write_lines(older, [{"type": "message", "id": "a", "usage": {"inputTokens": 7}}])
    assert adapter.snapshot().tokens == 7


def test_openclaw_cache_read_is_already_in_input(tmp_path):
    row = {"type": "message", "id": "a", "message": {"role": "assistant", "model": "gpt-test", "usage": {
        "input": 100, "cacheRead": 40, "cacheWrite": 10, "output": 20, "totalTokens": 130}}}
    write_lines(tmp_path / "main/sessions/session.jsonl", [row, row])
    write_lines(tmp_path / "notes.jsonl", [{**row, "id": "unrelated"}])
    snapshot = OpenClawAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (130, 110, 20)


def test_droid_settings_are_cumulative_with_separate_thinking(tmp_path):
    path = tmp_path / "session.settings.json"
    path.write_text(json.dumps({"model": "droid-test", "tokenUsage": {
        "inputTokens": 10, "outputTokens": 5, "cacheReadTokens": 3, "cacheCreationTokens": 2,
        "thinkingTokens": 4, "totalTokens": 24}}))
    adapter = DroidAdapter([tmp_path])
    snapshot = adapter.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (24, 15, 9)
    assert adapter.snapshot().tokens == 24
    path.write_text(json.dumps({"tokenUsage": {"inputTokens": 7, "outputTokens": 2}}))
    assert adapter.snapshot().tokens == 9


def test_hermes_explicit_session_ledger_is_read_only(tmp_path):
    path = tmp_path / "state.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE sessions (input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER, reasoning_tokens INTEGER, model TEXT, api_key TEXT)")
    db.execute("INSERT INTO sessions VALUES (10, 5, 3, 2, 4, 'hermes-test', 'CREDENTIAL_SENTINEL')")
    db.commit()
    db.close()
    before = path.read_bytes()
    snapshot = HermesAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (24, 15, 9)
    assert path.read_bytes() == before
    assert "CREDENTIAL_SENTINEL" not in json.dumps(asdict(snapshot), default=str)


def test_claude_science_excludes_demo_and_cache_subsets(tmp_path):
    db = sqlite3.connect(tmp_path / "operon-cli.db")
    db.execute("CREATE TABLE frames (input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER, aux_input_tokens INTEGER, aux_output_tokens INTEGER, aux_cache_read_tokens INTEGER, model TEXT, context_data TEXT)")
    db.execute("INSERT INTO frames VALUES (100, 20, 40, 10, 10, 3, 4, 'science-test', 'BODY_SENTINEL')")
    db.execute("INSERT INTO frames VALUES (NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'demo', ?)", (json.dumps({"input_tokens": 9999}),))
    db.commit()
    db.close()
    snapshot = ClaudeScienceAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (133, 110, 23)
    assert snapshot.model == "science-test"
    assert "BODY_SENTINEL" not in json.dumps(asdict(snapshot), default=str)


def test_claude_science_partial_cache_counters_are_not_lost(tmp_path):
    db = sqlite3.connect(tmp_path / "operon.db")
    db.execute("CREATE TABLE frames (cache_read_tokens INTEGER, output_tokens INTEGER)")
    db.execute("INSERT INTO frames VALUES (10, 2)")
    db.commit()
    db.close()
    assert ClaudeScienceAdapter([tmp_path]).snapshot().tokens == 12


@pytest.mark.parametrize("envelope", [False, True])
def test_cline_metrics_ignore_user_cache_and_reasoning_subsets(tmp_path, envelope):
    rows = [
        {"id": "a", "role": "assistant", "modelInfo": {"id": "cline-test"}, "metrics": {
            "inputTokens": 100, "outputTokens": 20, "cacheReadTokens": 40, "cacheWriteTokens": 10, "reasoningTokenCount": 5}},
        {"id": "a", "role": "assistant", "modelInfo": {"id": "cline-test"}, "metrics": {"inputTokens": 100, "outputTokens": 20}},
        {"role": "user", "metrics": {"inputTokens": 9999}},
    ]
    (tmp_path / "session.messages.json").write_text(json.dumps({"messages": rows} if envelope else rows))
    snapshot = ClineAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (120, 100, 20)
    assert snapshot.model == "cline-test"


def test_cline_imported_turns_are_excluded_by_metadata_timestamp(tmp_path):
    folder = tmp_path / "session"
    folder.mkdir()
    (folder / "session.json").write_text(json.dumps({"model": "test", "metadata": {
        "importedFrom": {"importedAt": "2026-10-03T00:00:00Z"}}}))
    (folder / "session.messages.json").write_text(json.dumps([
        {"id": "old", "role": "assistant", "ts": 1, "metrics": {"inputTokens": 9999}},
        {"id": "new", "role": "assistant", "ts": 1790985600001, "metrics": {"inputTokens": 10, "outputTokens": 2}},
    ]))
    assert ClineAdapter([tmp_path]).snapshot().tokens == 12


@pytest.mark.parametrize("adapter", [AStudioAdapter, EveryCodeAdapter])
def test_codex_forks_replace_cumulative_counters_instead_of_summing(tmp_path, adapter):
    def event(input_value, output_value):
        return {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": input_value, "cached_input_tokens": 40,
                "output_tokens": output_value, "reasoning_output_tokens": 5, "total_tokens": input_value + output_value},
            "last_token_usage": {"total_tokens": 9999}}}}
    write_lines(tmp_path / "rollout-session.jsonl", [
        {"type": "turn_context", "payload": {"model": "gpt-test"}}, event(100, 20), event(100, 20), event(120, 30)])
    snapshot = adapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (150, 120, 30)
    assert snapshot.model == "gpt-test"
    assert snapshot.context_percent is None


@pytest.mark.parametrize("adapter", [QoderAdapter, QoderCNAdapter])
def test_qoder_cli_uses_disjoint_cache_fields_and_ignores_credits(tmp_path, adapter):
    row = {"type": "assistant", "message": {"id": "a", "role": "assistant", "model": "qmodel", "usage": {
        "input_tokens": 10, "output_tokens": 2, "cache_read_input_tokens": 4, "cached_tokens": 4,
        "cache_creation_input_tokens": 3, "credits": 9999}}}
    write_lines(tmp_path / "session.jsonl", [row, row, {"type": "assistant", "message": {
        "id": "b", "role": "assistant", "usage": {"credits": 10000}}}])
    snapshot = adapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (19, 17, 2)


def test_kilo_reads_legacy_opencode_message_metadata(tmp_path):
    db = sqlite3.connect(tmp_path / "kilo.db")
    db.execute("CREATE TABLE message (data TEXT)")
    db.execute("INSERT INTO message VALUES (?)", (json.dumps({"role": "assistant", "modelID": "test", "tokens": {
        "input": 10, "output": 3, "reasoning": 2, "cache": {"read": 4, "write": 1}}}),))
    db.commit()
    db.close()
    assert KiloAdapter([tmp_path]).snapshot().tokens == 20


def test_all_selection_deduplicates_and_preserves_stable_auto():
    providers = [adapter.provider for adapter in make_adapters(["all", "auto", "minimax"])]
    assert set(providers) == set(PROVIDER_SPECS)
    assert len(providers) == len(PROVIDER_SPECS)
    assert auto_provider_names() == ["codex", "claude", "kimi", "opencode"]


def test_sqlite_reader_closes_connection_when_query_only_initialization_fails(tmp_path, monkeypatch):
    class FailingConnection:
        closed = False

        def execute(self, *args):
            raise sqlite3.OperationalError("cannot initialize")

        def close(self):
            self.closed = True

    connection = FailingConnection()
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connection)
    (tmp_path / "state.db").write_bytes(b"")
    snapshot = HermesAdapter([tmp_path]).snapshot()
    assert snapshot.tokens is None and snapshot.error
    assert connection.closed
