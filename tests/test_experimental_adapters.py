import json
import sqlite3
from pathlib import Path

from ai_cli_statusline.adapters import (
    AnythingLLMAdapter, CopilotAdapter, DevinAdapter, GooseAdapter, KiloAdapter,
    LmStudioAdapter, MimoAdapter, QoderAdapter, RooAdapter, ZCodeAdapter, ZedAdapter,
)


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
    db.execute("CREATE TABLE model_usage (input_tokens INTEGER, output_tokens INTEGER, reasoning_tokens INTEGER, cache_creation_input_tokens INTEGER, cache_read_input_tokens INTEGER, computed_total_tokens INTEGER, model TEXT)")
    db.execute("INSERT INTO model_usage VALUES (10, 4, 2, 1, 3, 20, 'z-model')")
    db.commit(); db.close()
    snapshot = ZCodeAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 20
    assert snapshot.input_tokens == 14
    assert snapshot.output_tokens == 6


def test_json_provider_fixtures(tmp_path: Path):
    payload = {"usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}, "model": "fixture"}
    (tmp_path / "usage.jsonl").write_text(json.dumps(payload) + "\n")
    for adapter in (
        LmStudioAdapter([tmp_path]), CopilotAdapter([tmp_path]),
        QoderAdapter([tmp_path]),
    ):
        snapshot = adapter.snapshot()
        assert snapshot.tokens == 15


def test_sqlite_provider_failure_is_explicit(tmp_path: Path):
    adapters = (
        KiloAdapter([tmp_path]), MimoAdapter([tmp_path]), ZedAdapter([tmp_path]),
        DevinAdapter([tmp_path]), AnythingLLMAdapter([tmp_path]),
    )
    for adapter in adapters:
        snapshot = adapter.snapshot()
        assert snapshot.tokens is None
        assert snapshot.error
