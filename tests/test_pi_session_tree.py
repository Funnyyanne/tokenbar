import json
import os
from dataclasses import asdict

import pytest

from ai_cli_statusline.adapters import OmoAdapter, OmpAdapter, PiAdapter
from ai_cli_statusline.cli import make_adapters


def message(identity="shared", **changes):
    usage = {"input": 10, "output": 4, "cacheRead": 2, "cacheWrite": 1,
        "reasoningTokens": 3, "reasoning": 3, **changes}
    return {"type": "message", "id": identity, "message": {
        "role": "assistant", "model": "test-model", "usage": usage,
        "content": [{"text": "PRIVATE_REPLY_SENTINEL", "usage": {"input": 999999}}]},
        "auth_token": "CREDENTIAL_SENTINEL"}


def write(path, records, modified):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(map(json.dumps, records)) + "\n")
    os.utime(path, (modified, modified))


@pytest.mark.parametrize("adapter,expected", [(OmoAdapter, 41), (OmpAdapter, 53)])
def test_pi_tree_sums_main_and_nested_subagents_once(tmp_path, monkeypatch, adapter, expected):
    main = tmp_path / "workspace" / "session.jsonl"
    child = main.with_suffix("") / "agent.jsonl"
    nested = child.with_suffix("") / "advisor.jsonl"
    write(main, [message(), message("main-only", input=5, output=1)], 1000)
    write(child, [message(), message("child", input=6, output=2)], 2000)
    write(nested, [message("advisor", input=1, output=0)], 3000)
    before = [path.read_bytes() for path in (main, child, nested)]
    monkeypatch.setattr(json, "loads", lambda *_args, **_kwargs: pytest.fail("decoded private body"))
    reader = adapter([tmp_path])
    snapshot = reader.snapshot()
    assert snapshot.tokens == expected
    assert (snapshot.input_tokens, snapshot.output_tokens) == (34, 7 if adapter is OmoAdapter else 19)
    assert snapshot.source == str(main)
    assert reader.snapshot().tokens == expected
    assert [path.read_bytes() for path in (main, child, nested)] == before
    assert "PRIVATE_" not in str(asdict(snapshot)) and "CREDENTIAL_" not in str(asdict(snapshot))


@pytest.mark.parametrize("adapter,expected", [(OmoAdapter, 25), (OmpAdapter, 28)])
def test_pi_tree_cross_file_correction_and_session_isolation(tmp_path, adapter, expected):
    main = tmp_path / "workspace" / "session.jsonl"
    child = main.with_suffix("") / "agent.jsonl"
    write(tmp_path / "workspace" / "old.jsonl", [message("old", input=99999)], 500)
    write(main, [message()], 1000)
    write(child, [message(output=6), message("child", input=5, output=1,
        cacheRead=0, cacheWrite=0, reasoningTokens=0, reasoning=0)], 2000)
    assert adapter([tmp_path]).snapshot().tokens == expected


@pytest.mark.parametrize("adapter,expected", [(OmoAdapter, 34), (OmpAdapter, 40)])
def test_pi_tree_groups_orphan_subagents_in_standard_sessions_root(tmp_path, adapter, expected):
    root = tmp_path / "sessions"
    child = root / "workspace" / "session" / "agent.jsonl"
    nested = child.with_suffix("") / "advisor.jsonl"
    write(child, [message("child")], 1000)
    write(nested, [message("nested")], 2000)
    snapshot = adapter([root]).snapshot()
    assert snapshot.tokens == expected
    assert snapshot.source == str(nested)


@pytest.mark.parametrize("adapter,expected", [(OmoAdapter, 17), (OmpAdapter, 20)])
def test_pi_tree_rebuilds_after_truncation_and_ignores_external_lineage(tmp_path, adapter, expected):
    root = tmp_path / "sessions"
    outside = tmp_path / "outside.jsonl"
    write(outside, [message("outside", input=99999)], 3000)
    main = root / "workspace" / "session.jsonl"
    child = main.with_suffix("") / "agent.jsonl"
    write(main, [{"type": "session", "parentSession": str(outside)}, message()], 1000)
    write(child, [message("child")], 2000)
    reader = adapter([root])
    assert reader.snapshot().tokens == expected * 2
    write(child, [], 2000)
    assert reader.snapshot().tokens == expected


@pytest.mark.parametrize("adapter", [OmoAdapter, OmpAdapter])
@pytest.mark.parametrize("changes", [{"input": True}, {"output": -1}, {"cacheRead": 1.5},
    {"cacheWrite": "bad"}, {"totalTokens": True}, {"input": {}, "output": None,
        "cacheRead": None, "cacheWrite": None, "reasoningTokens": None, "reasoning": None}])
def test_pi_tree_rejects_invalid_explicit_counts(tmp_path, adapter, changes):
    write(tmp_path / "session.jsonl", [message(**changes)], 1000)
    assert adapter([tmp_path]).snapshot().tokens is None


@pytest.mark.parametrize("adapter", [OmoAdapter, OmpAdapter])
def test_pi_tree_requires_valid_assistant_metadata(tmp_path, adapter):
    valid = message()
    write(tmp_path / "session.jsonl", [{**valid, "type": "custom"},
        {**valid, "message": {**valid["message"], "role": "user"}}], 1000)
    assert adapter([tmp_path]).snapshot().tokens is None


@pytest.mark.parametrize("adapter,expected", [(OmoAdapter, 34), (OmpAdapter, 40)])
def test_pi_tree_anonymous_observations_keep_distinct_file_identity(tmp_path, adapter, expected):
    main = tmp_path / "session.jsonl"
    write(main, [message(None)], 1000)
    write(main.with_suffix("") / "agent.jsonl", [message(None)], 2000)
    assert adapter([tmp_path]).snapshot().tokens == expected


@pytest.mark.parametrize("adapter", [OmoAdapter, OmpAdapter])
def test_pi_tree_zero_correction_removes_previous_usage(tmp_path, adapter):
    main = tmp_path / "workspace" / "session.jsonl"
    write(main, [message()], 1000)
    write(main.with_suffix("") / "agent.jsonl", [message(input=0, output=0,
        cacheRead=0, cacheWrite=0, reasoningTokens=0, reasoning=0)], 2000)
    assert adapter([tmp_path]).snapshot().tokens is None


@pytest.mark.parametrize("provider", ["omo", "omp"])
def test_pi_tree_custom_workspace_root_keeps_grouping(tmp_path, monkeypatch, provider):
    main = tmp_path / "session.jsonl"
    write(main, [message()], 1000)
    write(main.with_suffix("") / "agent.jsonl", [message("child")], 2000)
    monkeypatch.setenv("AI_CLI_STATUSLINE_SOURCES", json.dumps({provider: [str(tmp_path)]}))
    assert next(make_adapters([provider])).snapshot().tokens == (34 if provider == "omo" else 40)


def test_pi_reader_retains_independent_file_scope(tmp_path):
    main = tmp_path / "session.jsonl"
    write(main, [message()], 1000)
    write(main.with_suffix("") / "agent.jsonl", [message("child", input=5)], 2000)
    assert PiAdapter([tmp_path]).snapshot().tokens == 15
