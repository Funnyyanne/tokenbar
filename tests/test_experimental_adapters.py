import json
import sqlite3
from pathlib import Path

import pytest

from ai_cli_statusline.adapters import (
    AnythingLLMAdapter, CopilotAdapter, DevinAdapter, GeminiAdapter, GooseAdapter,
    KiloAdapter, OmpAdapter, PiAdapter, RooAdapter, ZCodeAdapter, ZedAdapter,
)
from ai_cli_statusline.cli import make_adapters
from ai_cli_statusline.providers import PROVIDER_SPECS


def test_goose_usage_ledger_fixture(tmp_path: Path):
    db_path = tmp_path / "sessions.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE usage_ledger (input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER, total_tokens INTEGER, model TEXT)")
    db.execute("INSERT INTO usage_ledger VALUES (100, 20, 30, 0, 150, 'goose-model')")
    db.commit(); db.close()
    snapshot = GooseAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 150
    assert snapshot.input_tokens == 130
    assert snapshot.output_tokens == 20
    assert snapshot.model == "goose-model"


def test_roo_history_item_fixture(tmp_path: Path):
    (tmp_path / "history_item.json").write_text(json.dumps({"tokensIn": 40, "tokensOut": 5, "cacheReads": 10, "cacheWrites": 2, "model": "roo-model"}))
    snapshot = RooAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 57
    assert snapshot.input_tokens == 52
    assert snapshot.output_tokens == 5


def test_zcode_schema_fixture(tmp_path: Path):
    db_path = tmp_path / "db.sqlite"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE model_usage (id TEXT, logical_request_id TEXT, attempt_index INTEGER, session_id TEXT, provider_id TEXT, status TEXT, started_at INTEGER, input_tokens INTEGER, output_tokens INTEGER, reasoning_tokens INTEGER, cache_creation_input_tokens INTEGER, cache_read_input_tokens INTEGER, model_id TEXT)")
    db.execute("INSERT INTO model_usage VALUES ('id', 'request', 0, 'session', 'builtin:zai', 'completed', 1000, 10, 4, 2, 1, 3, 'z-model')")
    db.commit(); db.close()
    snapshot = ZCodeAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 14
    assert snapshot.input_tokens == 10
    assert snapshot.output_tokens == 4


def test_gemini_saved_session_fixture(tmp_path: Path):
    path = tmp_path / "session-test.json"
    path.write_text(json.dumps({"messages": [
        {"type": "user", "content": "private prompt", "tokens": {"total": 999}},
        {"type": "gemini", "content": "private response", "model": "gemini-test", "tokens": {"input": 12, "output": 3, "cached": 2, "thoughts": 1, "total": 18}},
    ]}))
    snapshot = GeminiAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 18
    assert snapshot.input_tokens == 12
    assert snapshot.output_tokens == 4
    assert snapshot.model == "gemini-test"


def test_pi_and_omp_read_only_assistant_usage(tmp_path: Path):
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join([
        json.dumps({"type": "message", "message": {"role": "user", "usage": {"input": 999}}}),
        json.dumps({"type": "message", "message": {"role": "assistant", "model": "pi-test", "usage": {"input": 10, "output": 3, "cacheRead": 4, "cacheWrite": 2, "cost": {"input": 99}}}}),
    ]) + "\n")
    for adapter in (PiAdapter([tmp_path]), OmpAdapter([tmp_path])):
        snapshot = adapter.snapshot()
        assert snapshot.tokens == 19
        assert snapshot.input_tokens == 16
        assert snapshot.output_tokens == 3


def test_copilot_reads_chat_spans_and_deduplicates_span_id(tmp_path: Path):
    path = tmp_path / "copilot.jsonl"
    chat = {"spanId": "span-1", "attributes": {
        "gen_ai.operation.name": "chat",
        "gen_ai.response.id": "response-1",
        "gen_ai.request.model": "copilot-test",
        "gen_ai.usage.input_tokens": {"intValue": "20"},
        "gen_ai.usage.output_tokens": 5,
        "gen_ai.usage.cache_read.input_tokens": 3,
        "gen_ai.usage.cache_creation.input_tokens": 2,
    }}
    root = {"spanId": "root", "attributes": {"gen_ai.operation.name": "invoke_agent", "gen_ai.usage.input_tokens": 20}}
    path.write_text("\n".join(map(json.dumps, (root, chat, chat))) + "\n")
    snapshot = CopilotAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 27
    assert snapshot.input_tokens == 22
    assert snapshot.output_tokens == 5


def test_sqlite_provider_failure_is_explicit(tmp_path: Path):
    adapters = (
        KiloAdapter([tmp_path]), ZedAdapter([tmp_path]),
        DevinAdapter([tmp_path]), AnythingLLMAdapter([tmp_path]),
    )
    for adapter in adapters:
        snapshot = adapter.snapshot()
        assert snapshot.tokens is None
        assert snapshot.error


def test_all_experimental_readers_report_empty_sources(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("COPILOT_OTEL_FILE_EXPORTER_PATH", raising=False)
    adapters = (
        GeminiAdapter([tmp_path]), PiAdapter([tmp_path]), OmpAdapter([tmp_path]),
        GooseAdapter([tmp_path]), RooAdapter([tmp_path]), CopilotAdapter([tmp_path]),
        KiloAdapter([tmp_path]), ZedAdapter([tmp_path]), AnythingLLMAdapter([tmp_path]),
        DevinAdapter([tmp_path]), ZCodeAdapter([tmp_path]),
    )
    for adapter in adapters:
        snapshot = adapter.snapshot()
        assert snapshot.tokens is None
        assert snapshot.error


def test_json_path_sqlite_readers_extract_metrics_without_returning_body(tmp_path: Path):
    anything = tmp_path / "anythingllm.db"
    db = sqlite3.connect(anything)
    db.execute("CREATE TABLE workspace_chats (response TEXT)")
    db.execute("INSERT INTO workspace_chats VALUES (?)", (json.dumps({"textResponse": "private response", "metrics": {"prompt_tokens": 30, "completion_tokens": 7}}),))
    db.commit(); db.close()
    snapshot = AnythingLLMAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 37

    anything.unlink()
    devin = tmp_path / "sessions.db"
    db = sqlite3.connect(devin)
    db.execute("CREATE TABLE message_nodes (chat_message TEXT)")
    db.execute("INSERT INTO message_nodes VALUES (?)", (json.dumps({"role": "assistant", "content": "private response", "metadata": {"request_id": "request", "started_generation_at": "2026-10-03T00:00:00Z", "generation_model": "devin-test", "metrics": {"input_tokens": 40, "output_tokens": 8, "cache_read_tokens": 2}}}),))
    db.commit(); db.close()
    snapshot = DevinAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 50
    assert snapshot.model == "devin-test"


def test_kilo_session_usage_schema(tmp_path: Path):
    db = sqlite3.connect(tmp_path / "kilo.db")
    db.execute("CREATE TABLE session (tokens_input INTEGER, tokens_output INTEGER, tokens_reasoning INTEGER, tokens_cache_read INTEGER, tokens_cache_write INTEGER, model TEXT)")
    db.execute("INSERT INTO session VALUES (10, 3, 2, 4, 1, 'kilo-test')")
    db.commit(); db.close()
    snapshot = KiloAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 20
    assert snapshot.output_tokens == 5


def test_zed_legacy_json_thread_usage(tmp_path: Path):
    db = sqlite3.connect(tmp_path / "threads.db")
    db.execute("CREATE TABLE threads (data TEXT, data_type TEXT)")
    db.execute("INSERT INTO threads VALUES (?, 'json')", (json.dumps({"request_token_usage": {"r1": {"input_tokens": 10, "output_tokens": 2}}}),))
    db.commit(); db.close()
    snapshot = ZedAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 12


def test_unverified_providers_return_explicit_unavailable():
    for name in ("craft",):
        snapshot = next(make_adapters([name])).snapshot()
        assert snapshot.maturity == "planned"
        assert snapshot.tokens is None
        assert snapshot.error


def test_provider_registry_covers_every_declared_provider():
    for name, spec in PROVIDER_SPECS.items():
        adapter = next(make_adapters([name]))
        assert adapter.provider == name
        assert adapter.label == spec.label
        assert getattr(adapter, "maturity", "stable") == spec.maturity


@pytest.mark.parametrize("valid_count, invalid_count", [(25, 0), (1, 25)])
def test_zed_scans_all_threads(tmp_path: Path, valid_count, invalid_count):
    with sqlite3.connect(tmp_path / "threads.db") as db:
        db.execute("CREATE TABLE threads (data TEXT, data_type TEXT, updated_at INTEGER)")
        for index in range(valid_count):
            db.execute("INSERT INTO threads VALUES (?, 'json', ?)", (
                json.dumps({"request_token_usage": {"r1": {"input_tokens": 10, "output_tokens": 2}}}), index,
            ))
        for index in range(invalid_count):
            db.execute("INSERT INTO threads VALUES ('compressed', 'zstd', ?)", (100 + index,))
            db.execute("INSERT INTO threads VALUES ('{}', 'json', ?)", (200 + index,))
    snapshot = ZedAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == valid_count * 12
    assert snapshot.input_tokens == valid_count * 10
    assert snapshot.output_tokens == valid_count * 2


@pytest.mark.parametrize("provider, adapter_type", [
    ("gemini", GeminiAdapter), ("pi", PiAdapter), ("omp", OmpAdapter),
])
@pytest.mark.parametrize("with_usage", [True, False])
def test_registered_session_reader_uses_custom_roots(tmp_path: Path, monkeypatch, provider, adapter_type, with_usage):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    custom = home / "custom"
    custom.mkdir()
    monkeypatch.setenv("AI_CLI_STATUSLINE_SOURCES", json.dumps({provider.upper(): [str(custom)]}))
    if with_usage:
        if provider == "gemini":
            (custom / "session-test.json").write_text(json.dumps({"messages": [
                {"type": "gemini", "tokens": {"input": 10, "output": 2, "total": 12}},
            ]}))
        else:
            (custom / "session.jsonl").write_text(json.dumps({"type": "message", "message": {
                "role": "assistant", "usage": {"input": 10, "output": 2},
            }}) + "\n")
    adapter = next(make_adapters([provider]))
    assert isinstance(adapter, adapter_type)
    assert adapter.roots == [custom]
    snapshot = adapter.snapshot()
    assert snapshot.tokens == (12 if with_usage else None)
    assert bool(snapshot.error) == (not with_usage)
