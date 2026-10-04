import json
import os

import pytest
import zstandard

from ai_cli_statusline.adapters import DeepSeekAdapter


def header():
    return {"type": "request/header", "seq": 0, "data": {"header": {"config": {"model": "deepseek/test-model"}}}}


def message(seq=1, **usage):
    return {"type": "assistant/message", "seq": seq, "time": 1784357000000,
        "data": {"message": {"id": f"message-{seq}", "content": "PRIVATE_REPLY_SENTINEL"},
            "usage": {"inputTokens": 100, "outputTokens": 40, "cacheReadTokens": 50,
                "cacheWriteTokens": 10, "reasoningTokens": 20, **usage}}}


def encode(records):
    return ("\n".join(map(json.dumps, records)) + "\n").encode()


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("version", ["", ".v3"])
def test_deepseek_disjoint_usage_and_seq_dedup_across_encodings(tmp_path, compressed, version, monkeypatch):
    content = encode([header(), message(), message()])
    path = tmp_path / (f"session{version}.jsonl" + (".zstd" if compressed else ""))
    if compressed:
        compressor = zstandard.ZstdCompressor()
        # Independent frames split inside a JSON string and across lines.
        content = b"".join(compressor.compress(part) for part in (content[:53], content[53:113], content[113:]))
    path.write_bytes(content)
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded private body"))
    adapter = DeepSeekAdapter([tmp_path])
    snapshot = adapter.snapshot()
    assert (snapshot.tokens, snapshot.input_tokens, snapshot.output_tokens) == (220, 160, 60)
    assert snapshot.model == "test-model"
    assert adapter.snapshot().tokens == 220
    assert path.read_bytes() == content


def test_deepseek_corrected_observation_and_truncated_repaired_interior(tmp_path):
    path = tmp_path / "session.v3.jsonl"
    first = {**message(0), "type": "message/assistant"}
    prefix = encode([header(), first])
    later = encode([message(1)])
    path.write_bytes(prefix + b'{"type": "message/assistant", broken\n' + later)
    adapter = DeepSeekAdapter([tmp_path])
    assert adapter.snapshot().tokens == 220
    path.write_bytes(prefix + encode([message(0, inputTokens=120), message(1)]))
    assert adapter.snapshot().tokens == 460
    path.write_bytes(encode([header(), message(1, inputTokens=10)]))
    assert adapter.snapshot().tokens == 130


def test_deepseek_active_version_wins_tie_without_counting_legacy_mirror(tmp_path):
    old = tmp_path / "session.jsonl"
    active = tmp_path / "session.v3.jsonl.zstd"
    old.write_bytes(encode([header(), message(inputTokens=999)]))
    active.write_bytes(zstandard.ZstdCompressor().compress(encode([header(), message()])))
    os.utime(old, ns=(1000000, 1000000))
    os.utime(active, ns=(1000000, 1000000))
    snapshot = DeepSeekAdapter([tmp_path]).snapshot()
    assert snapshot.tokens == 220
    assert snapshot.source.endswith("session.v3.jsonl.zstd")


@pytest.mark.parametrize("content", [b"not zstd", zstandard.ZstdCompressor().compress(encode([header(), message()]))[:-1]])
def test_deepseek_corrupt_or_unfinished_frame_is_unavailable(tmp_path, content):
    (tmp_path / "session.jsonl.zstd").write_bytes(content)
    snapshot = DeepSeekAdapter([tmp_path]).snapshot()
    assert snapshot.tokens is None
    assert snapshot.error


@pytest.mark.parametrize("usage", [{"inputTokens": -1}, {"outputTokens": True}, {"cacheReadTokens": 1.5}])
def test_deepseek_invalid_counts_do_not_become_valid_partial_usage(tmp_path, usage):
    (tmp_path / "session.jsonl").write_bytes(encode([header(), message(**usage)]))
    assert DeepSeekAdapter([tmp_path]).snapshot().tokens is None


def test_deepseek_model_precedence_root_usage_and_nonassistant_filter(tmp_path):
    actual = message()
    actual["type"] = "message/assistant"
    actual["usage"] = actual["data"].pop("usage")
    actual["data"]["message"]["source"] = {"model": "deepseek/actual-model"}
    user = {**message(2), "type": "message/user"}
    (tmp_path / "session.v3.jsonl").write_bytes(encode([header(), user, actual]))
    assert DeepSeekAdapter([tmp_path]).snapshot().model == "actual-model"
    assert DeepSeekAdapter([tmp_path]).snapshot().tokens == 220


def test_deepseek_decoder_enforces_bounded_output(tmp_path, monkeypatch):
    import ai_cli_statusline.adapters.deepseek as module
    monkeypatch.setattr(module, "_MAX_TEXT", 16)
    (tmp_path / "session.jsonl.zstd").write_bytes(zstandard.ZstdCompressor().compress(encode([header(), message()])))
    assert DeepSeekAdapter([tmp_path]).snapshot().tokens is None
