import json
from dataclasses import asdict

import pytest

from ai_cli_statusline.cli import make_adapters


def grok_adapter(root, monkeypatch):
    monkeypatch.setenv("AI_CLI_STATUSLINE_SOURCES", json.dumps({"grok": [str(root)]}))
    return next(make_adapters(["grok"]))


def turn(usage, identity="turn", **update):
    return {"method": "session/update", "params": {"_meta": {"eventId": identity},
        "update": {"sessionUpdate": "turn_completed", "usage": usage, **update}}}


def write_turns(path, records):
    path.write_text("\n".join(map(json.dumps, records)) + "\n")


def test_grok_prefers_per_model_usage_over_mirrored_aggregate_and_context(tmp_path, monkeypatch):
    usage = {"inputTokens": 100, "outputTokens": 20, "cachedReadTokens": 30,
        "cacheCreationTokens": 10, "reasoningTokens": 5, "totalTokens": 120}
    record = turn({**usage, "modelUsage": {"grok-test": usage}})
    write_turns(tmp_path / "updates.jsonl", [
        {"params": {"_meta": {"totalTokens": 900000}, "update": {"sessionUpdate": "agent_thought_chunk"}}},
        record, record,
    ])
    (tmp_path / "signals.json").write_text(json.dumps({"primaryModelId": "fallback-model",
        "contextTokensUsed": 900000, "totalTokensBeforeCompaction": 1000000, "auth": "CREDENTIAL_SENTINEL"}))
    snapshot = grok_adapter(tmp_path, monkeypatch).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (120, 100, 20)
    assert snapshot.model == "grok-test"
    assert snapshot.maturity == "experimental"
    assert "CREDENTIAL_SENTINEL" not in json.dumps(asdict(snapshot), default=str)


def test_grok_snake_input_is_disjoint_and_corrected_turn_replaces_old_models(tmp_path, monkeypatch):
    write_turns(tmp_path / "updates.jsonl", [
        turn({"modelUsage": {"old-model": {"inputTokens": 100, "outputTokens": 20}}}),
        turn({"modelUsage": {"new-model": {"input_tokens": 70, "output_tokens": 20,
            "cached_input_tokens": 30, "cache_creation_input_tokens": 10, "reasoning_output_tokens": 5}}}),
    ])
    adapter = grok_adapter(tmp_path, monkeypatch)
    snapshot = adapter.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (130, 110, 20)
    assert snapshot.model == "new-model"
    assert adapter.snapshot().tokens == 130


def test_grok_partial_bad_models_fall_back_to_reported_aggregate(tmp_path, monkeypatch):
    write_turns(tmp_path / "updates.jsonl", [turn({"inputTokens": 10, "outputTokens": 2,
        "modelUsage": {"broken": None, "wrong": {"inputTokens": -1, "outputTokens": 2}}})])
    (tmp_path / "signals.json").write_text(json.dumps({"primaryModelId": "signal-model"}))
    snapshot = grok_adapter(tmp_path, monkeypatch).snapshot()
    assert snapshot.tokens == 12
    assert snapshot.model == "signal-model"


@pytest.mark.parametrize("invalid", [None, "bad", [], {}, {"inputTokens": -1},
    {"inputTokens": True}, {"inputTokens": 1.5}, {"inputTokens": {}, "outputTokens": 2},
    {"inputTokens": [], "outputTokens": 2}])
def test_grok_mixed_valid_invalid_models_use_full_aggregate(tmp_path, monkeypatch, invalid):
    write_turns(tmp_path / "updates.jsonl", [turn({"inputTokens": 100, "outputTokens": 20,
        "modelUsage": {"valid-model": {"inputTokens": 10, "outputTokens": 2}, "broken": invalid}})])
    (tmp_path / "signals.json").write_text(json.dumps({"primaryModelId": "signal-model"}))
    snapshot = grok_adapter(tmp_path, monkeypatch).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (120, 100, 20)
    assert snapshot.model == "signal-model"


def test_grok_incomplete_models_without_valid_aggregate_are_unavailable(tmp_path, monkeypatch):
    write_turns(tmp_path / "updates.jsonl", [turn({"inputTokens": -1,
        "modelUsage": {"valid": {"inputTokens": 10, "outputTokens": 2}, "broken": None}})])
    assert grok_adapter(tmp_path, monkeypatch).snapshot().tokens is None


def test_grok_zero_usage_model_does_not_make_complete_details_partial(tmp_path, monkeypatch):
    write_turns(tmp_path / "updates.jsonl", [turn({"inputTokens": 100, "outputTokens": 20,
        "modelUsage": {"idle": {"inputTokens": 0, "outputTokens": 0},
            "valid": {"inputTokens": 10, "outputTokens": 2}}})])
    assert grok_adapter(tmp_path, monkeypatch).snapshot().tokens == 12


def test_grok_all_zero_model_details_fall_back_to_positive_aggregate(tmp_path, monkeypatch):
    write_turns(tmp_path / "updates.jsonl", [turn({"inputTokens": 100, "outputTokens": 20,
        "modelUsage": {"idle": {"inputTokens": 0, "outputTokens": 0}}})])
    assert grok_adapter(tmp_path, monkeypatch).snapshot().tokens == 120


def test_grok_incomplete_corrected_models_replace_previous_turn(tmp_path, monkeypatch):
    write_turns(tmp_path / "updates.jsonl", [
        turn({"modelUsage": {"old": {"inputTokens": 10, "outputTokens": 2}}}),
        turn({"inputTokens": 100, "outputTokens": 20,
            "modelUsage": {"valid": {"inputTokens": 10, "outputTokens": 2}, "broken": None}}),
    ])
    reader = grok_adapter(tmp_path, monkeypatch)
    assert reader.snapshot().tokens == reader.snapshot().tokens == 120


@pytest.mark.parametrize("record", [
    {"params": {"_meta": {"totalTokens": 10000}}},
    turn({"inputTokens": 100, "outputTokens": 2}, sessionUpdate="agent_message_chunk"),
    turn({"inputTokens": True, "outputTokens": "bad"}),
    turn({"inputTokens": -1, "outputTokens": 2}),
    turn({"costUsdTicks": 100, "modelCalls": 1}),
    {"content": turn({"inputTokens": 100, "outputTokens": 2})},
])
def test_grok_context_estimates_body_and_invalid_usage_are_unavailable(tmp_path, monkeypatch, record):
    write_turns(tmp_path / "updates.jsonl", [record])
    snapshot = grok_adapter(tmp_path, monkeypatch).snapshot()
    assert snapshot.tokens is None
    assert snapshot.error
