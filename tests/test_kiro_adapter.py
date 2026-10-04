import json

import pytest

from ai_cli_statusline.cli import make_adapters


_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def fixture(root, turns, *, name=_UUID + ".json"):
    directory = root / "cli"
    directory.mkdir(exist_ok=True)
    path = directory / name
    record = {"session_id": _UUID, "auth_token": "CREDENTIAL_SENTINEL", "session_state": {
        "conversation": "PRIVATE_PROMPT_SENTINEL", "rts_model_state": {"model_info": {"model_id": "kiro-test"}},
        "conversation_metadata": {"user_turn_metadatas": turns}}}
    path.write_text(json.dumps(record))
    return path


def turn(loop=0, **values):
    return {"loop_id": {"rand": loop}, "message_ids": ["message"], "request_start_timestamp_ms": 1784357000000,
        "input_token_count": 100, "output_token_count": 20, **values}


def adapter(root, monkeypatch):
    monkeypatch.setenv("AI_CLI_STATUSLINE_SOURCES", json.dumps({"kiro": [str(root)]}))
    return next(make_adapters(["kiro"]))


def test_kiro_explicit_counters_preserve_zero_loop_and_replace_corrections(tmp_path, monkeypatch):
    path = fixture(tmp_path, [turn(), turn(output_token_count=25), turn(1)])
    before = path.read_bytes()
    reader = adapter(tmp_path, monkeypatch)
    snapshot = reader.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (245, 200, 45)
    assert snapshot.model == "kiro-test"
    assert snapshot.maturity == "experimental"
    assert reader.snapshot().tokens == 245
    assert path.read_bytes() == before


def test_kiro_session_fields_are_scalar_and_no_body_is_decoded(tmp_path, monkeypatch):
    fixture(tmp_path, [turn(model_id="turn-model")])
    reader = adapter(tmp_path, monkeypatch)
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded private body"))
    assert reader.snapshot().model == "turn-model"


@pytest.mark.parametrize("values", [
    {"input_token_count": 0, "output_token_count": 0, "user_prompt_length": 999999, "response_size": 999999},
    {"input_token_count": None}, {"output_token_count": -1}, {"input_token_count": True},
    {"input_token_count": 1.5}, {"request_start_timestamp_ms": None, "end_timestamp": "bad"},
])
def test_kiro_missing_invalid_and_estimated_counts_are_unavailable(tmp_path, monkeypatch, values):
    fixture(tmp_path, [turn(**values)])
    assert adapter(tmp_path, monkeypatch).snapshot().tokens is None


def test_kiro_opaque_loop_seed_and_message_fallback(tmp_path, monkeypatch):
    fixture(tmp_path, [turn(loop_id={"seed": 0}, output_token_count=25),
        turn(loop_id={}, message_ids=["separate"], start_timestamp="2026-10-03T00:00:00Z", request_start_timestamp_ms=None)])
    assert adapter(tmp_path, monkeypatch).snapshot().tokens == 245


def test_kiro_current_jsonl_credits_and_unrelated_json_are_not_token_sources(tmp_path, monkeypatch):
    session = tmp_path / "workspace" / "sess_opaque"
    session.mkdir(parents=True)
    (session / "messages.jsonl").write_text(json.dumps({"type": "usage_summary", "credits": 1.5,
        "content": "PRIVATE_REPLY_SENTINEL", "usage": {"input_tokens": 999999}}) + "\n")
    fixture(tmp_path, [turn()], name="scratch.json")
    snapshot = adapter(tmp_path, monkeypatch).snapshot()
    assert snapshot.tokens is None
    assert snapshot.error
