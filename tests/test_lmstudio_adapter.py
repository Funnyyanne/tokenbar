import json

import pytest

from ai_cli_statusline.adapters import LMStudioAdapter


def response(identity="chatcmpl-1", **usage):
    value = {"id": identity, "model": "local-model", "choices": [{"message": {"content":
        'PRIVATE_REPLY_SENTINEL with \\"usage\\": {\\"input_tokens\\": 999}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": 30, "cache_write_tokens": 10},
            "completion_tokens_details": {"reasoning_tokens": 5}, **usage}}
    return '[2026-10-03 19:00:00][INFO][local-model]\nFinal response: ' + json.dumps(value, indent=2) + '\n'


def test_lmstudio_final_response_projection_and_duplicate_correction(tmp_path, monkeypatch):
    content = response() + response() + response(completion_tokens=25, total_tokens=125)
    path = tmp_path / "server.log"
    path.write_text(content)
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded private body"))
    adapter = LMStudioAdapter([tmp_path])
    snapshot = adapter.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (125, 100, 25)
    assert snapshot.model == "local-model"
    assert adapter.snapshot().tokens == 125
    assert path.read_text() == content


def test_lmstudio_responses_api_reported_total_and_mixed_text(tmp_path):
    record = {"id": "resp_1", "model": "reasoning-model", "output": [{"content": "PRIVATE_REPLY_SENTINEL"}],
        "usage": {"input_tokens": 70, "output_tokens": 20, "total_tokens": 100,
            "input_tokens_details": {"cached_tokens": 30}, "output_tokens_details": {"reasoning_tokens": 8}}}
    (tmp_path / "server.log").write_text('Some unrelated text {"usage": {"total_tokens": 999999}}\n' +
        '[2026-10-03 19:00:00][INFO] Final response: ' + json.dumps(record) + '\n')
    snapshot = LMStudioAdapter([tmp_path]).snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (100, 80, 20)
    assert snapshot.model == "reasoning-model"


def test_lmstudio_keeps_usage_after_body_larger_than_eight_mib(tmp_path):
    record = {"id": "chatcmpl-large", "model": "local-model", "choices": [{"content": "x" * (8 * 1024 * 1024 + 100)}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2}}
    (tmp_path / "server.log").write_text('Final response: ' + json.dumps(record) + '\n')
    assert LMStudioAdapter([tmp_path]).snapshot().tokens == 12


def test_lmstudio_marker_and_json_strings_survive_chunk_boundary(tmp_path):
    path = tmp_path / "server.log"
    path.write_text("x" * (64 * 1024 - 9) + "\n" + response())
    assert LMStudioAdapter([tmp_path]).snapshot().tokens == 120


def test_lmstudio_aggregates_rotated_logs_and_deduplicates_response_mirrors(tmp_path):
    (tmp_path / "one.log").write_text(response("chatcmpl-shared") + response("chatcmpl-older"))
    (tmp_path / "two.log").write_text(response("chatcmpl-shared") + response("chatcmpl-newer"))
    assert LMStudioAdapter([tmp_path]).snapshot().tokens == 360


@pytest.mark.parametrize("text", [
    'Final response: {"id":"resp_1", "usage": {"input_tokens":100',
    '{"content": {"usage": {"total_tokens":999999}}}\n',
    response(prompt_tokens=True),
    response(completion_tokens=-1),
])
def test_lmstudio_incomplete_body_usage_and_invalid_counts_are_unavailable(tmp_path, text):
    (tmp_path / "server.log").write_text(text)
    assert LMStudioAdapter([tmp_path]).snapshot().tokens is None
