from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from threading import Thread

import pytest

from ai_cli_statusline.integrations import snapshot_from_statusline
from ai_cli_statusline.integrations import setup_claude, setup_kimi
from ai_cli_statusline.integrations import _read_stdin_json
from ai_cli_statusline.cache import read_snapshot, write_snapshot
from ai_cli_statusline.models import Snapshot
from ai_cli_statusline.cli import collect, main
from ai_cli_statusline.adapters.kimi import KimiAdapter


def test_claude_statusline_snapshot() -> None:
    snapshot = snapshot_from_statusline(
        "claude",
        "Claude",
        {
            "model": {"display_name": "Sonnet"},
            "context_window": {
                "used_percentage": 25,
                "context_window_size": 200_000,
                "current_usage": {"input_tokens": 10_000, "output_tokens": 500},
            },
            "rate_limits": {"five_hour": {"used_percentage": 40}},
        },
    )
    assert snapshot.model == "Sonnet"
    assert snapshot.context_used == 50_000
    assert snapshot.context_percent == 25
    assert snapshot.rate_limits[0].used_percent == 40


def test_read_stdin_json_does_not_block_on_interactive_terminal(monkeypatch) -> None:
    class TTYInput(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("sys.stdin", TTYInput())
    assert _read_stdin_json() == {}


def test_setup_claude_preserves_existing_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    path = tmp_path / "claude" / "settings.json"
    path.parent.mkdir()
    path.write_text('{"theme":"dark"}\n', encoding="utf-8")
    setup_claude(executable="ai-cli-statusline")
    assert '"theme": "dark"' in path.read_text(encoding="utf-8")
    assert "statusLine" in path.read_text(encoding="utf-8")
    assert path.with_suffix(".json.bak").exists()


def test_setup_kimi_preserves_other_toml_sections(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "kimi"))
    path = tmp_path / "kimi" / "tui.toml"
    path.parent.mkdir()
    path.write_text('theme = "dark"\n[editor]\ncommand = "vim"\n', encoding="utf-8")
    setup_kimi(executable="ai-cli-statusline")
    content = path.read_text(encoding="utf-8")
    assert 'theme = "dark"' in content
    assert '[editor]' in content
    assert '[status_line]' in content


def test_setup_kimi_inserts_command_inside_existing_status_section(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "kimi"))
    path = tmp_path / "kimi" / "tui.toml"
    path.parent.mkdir()
    path.write_text('[status_line]\nitems = ["model"]\n\n[editor]\ncommand = "vim"\n', encoding="utf-8")
    setup_kimi(executable="tokenbar", force=True)
    content = path.read_text(encoding="utf-8")
    assert '[status_line]\nitems = ["model"]\ncommand = "tokenbar kimi-statusline"\n\n[editor]' in content


def test_setup_kimi_recognizes_status_section_with_trailing_comment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "kimi"))
    path = tmp_path / "kimi" / "tui.toml"
    path.parent.mkdir()
    path.write_text('[status_line] # keep this note\ncommand = "old"\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"已存在 \[status_line\]"):
        setup_kimi(executable="tokenbar")

    setup_kimi(executable="tokenbar", force=True)
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["status_line"]["command"] == "tokenbar kimi-statusline"


def test_setup_kimi_does_not_write_invalid_toml(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "kimi"))
    path = tmp_path / "kimi" / "tui.toml"
    path.parent.mkdir()
    original = '[status_line] # repair command only\ncommand = "old"\nbroken = [\n'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(RuntimeError, match="不是有效 TOML"):
        setup_kimi(executable="tokenbar", force=True)

    assert path.read_text(encoding="utf-8") == original
    assert not path.with_suffix(".toml.bak").exists()


def test_setup_kimi_ignores_commented_status_line_section(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "kimi"))
    path = tmp_path / "kimi" / "tui.toml"
    path.parent.mkdir()
    path.write_text('# [status_line]\n# command = "x"\n', encoding="utf-8")
    setup_kimi(executable="tokenbar", force=True)
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["status_line"]["command"] == "tokenbar kimi-statusline"
    assert "command" not in data


def test_setup_kimi_force_removes_duplicate_commands(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path / "kimi"))
    path = tmp_path / "kimi" / "tui.toml"
    path.parent.mkdir()
    path.write_text('[status_line]\ncommand = "old-a"\ncommand = "old-b"\n', encoding="utf-8")
    setup_kimi(executable="tokenbar", force=True)
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["status_line"]["command"] == "tokenbar kimi-statusline"


def test_render_stdin_statusline_respects_no_color(tmp_path, monkeypatch, capsys) -> None:
    import io

    from ai_cli_statusline.integrations import render_stdin_statusline

    monkeypatch.setattr("sys.stdin", io.StringIO('{"model": {"display_name": "K3"}}'))
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path))
    render_stdin_statusline("kimi", "Kimi")
    assert "\033[" not in capsys.readouterr().out


def test_partial_statusline_event_preserves_cached_usage(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path))
    write_snapshot(Snapshot(provider="kimi", label="Kimi", model="old", tokens=90, input_tokens=80, output_tokens=10, context_used=50, context_window=100))

    write_snapshot(snapshot_from_statusline("kimi", "Kimi", {"model": {"display_name": "new"}}))

    cached = read_snapshot("kimi", "Kimi")
    assert cached is not None
    assert cached.model == "new"
    assert cached.tokens == 90
    assert cached.context_used == 50


def test_expired_cache_is_explicitly_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path))
    old = datetime.now(timezone.utc) - timedelta(hours=25)
    write_snapshot(Snapshot(provider="kimi", label="Kimi", updated_at=old, tokens=90))

    cached = read_snapshot("kimi", "Kimi", max_age_seconds=24 * 60 * 60)

    assert cached is not None
    assert cached.stale is True
    assert cached.error == "缓存已过期"


def test_concurrent_cache_writes_are_atomic(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path))
    errors: list[Exception] = []

    def write(index: int) -> None:
        try:
            write_snapshot(Snapshot(provider="kimi", label="Kimi", tokens=index + 1))
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [Thread(target=write, args=(index,)) for index in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert read_snapshot("kimi", "Kimi") is not None


def test_concurrent_partial_cache_writes_merge_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path))
    threads = [
        Thread(target=write_snapshot, args=(Snapshot(provider="kimi", label="Kimi", model="K3"),)),
        Thread(target=write_snapshot, args=(Snapshot(provider="kimi", label="Kimi", tokens=12),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    cached = read_snapshot("kimi", "Kimi")
    assert cached is not None
    assert cached.model == "K3"
    assert cached.tokens == 12


def test_invalid_statusline_percentage_is_ignored() -> None:
    snapshot = snapshot_from_statusline(
        "kimi",
        "Kimi",
        {"context_window": {"used_percentage": "invalid", "context_window_size": 100}},
    )
    assert snapshot.context_used is None


def test_invalid_statusline_container_types_are_ignored() -> None:
    snapshot = snapshot_from_statusline(
        "kimi",
        "Kimi",
        {"context_window": "invalid", "rate_limits": 42},
    )
    assert snapshot.tokens is None
    assert snapshot.rate_limits == []


def test_unknown_provider_is_reported_without_traceback(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(["status", "--providers", "unknown", "--no-color"])

    captured = capsys.readouterr()
    assert result.value.code == 2
    assert "不支持的 provider：unknown" in captured.err
    assert "Traceback" not in captured.err


def test_status_returns_failure_when_snapshot_has_no_data(monkeypatch, capsys) -> None:
    monkeypatch.setattr("ai_cli_statusline.cli.collect", lambda _names: [Snapshot(provider="codex", label="Codex")])
    assert main(["status", "--providers", "codex", "--no-color"]) == 1
    assert "Codex" in capsys.readouterr().out


def test_corrupt_cache_is_ignored_without_traceback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path / "home"))
    cache = tmp_path / "home" / "cache" / "kimi.json"
    cache.parent.mkdir(parents=True)
    cache.write_text("{broken", encoding="utf-8")

    snapshot = KimiAdapter([tmp_path / "missing"]).snapshot()

    assert snapshot.error == "未找到可识别 token 字段"


def test_wrong_cache_field_types_are_ignored(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path / "home"))
    cache = tmp_path / "home" / "cache" / "kimi.json"
    cache.parent.mkdir(parents=True)
    cache.write_text('{"rate_limits": 42, "updated_at": []}', encoding="utf-8")

    snapshot = KimiAdapter([tmp_path / "missing"]).snapshot()

    assert snapshot.error == "未找到可识别 token 字段"
    assert snapshot.rate_limits == []


def test_cache_without_valid_timestamp_is_not_treated_as_fresh(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AI_CLI_STATUSLINE_HOME", str(tmp_path / "home"))
    cache = tmp_path / "home" / "cache" / "kimi.json"
    cache.parent.mkdir(parents=True)
    cache.write_text('{"tokens": 99}', encoding="utf-8")

    snapshot = KimiAdapter([tmp_path / "missing"]).snapshot()

    assert snapshot.tokens is None
    assert snapshot.error == "未找到可识别 token 字段"


def test_one_provider_exception_does_not_break_other_results(monkeypatch) -> None:
    monkeypatch.setattr("ai_cli_statusline.adapters.codex.CodexAdapter.snapshot", lambda _self: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr("ai_cli_statusline.adapters.claude.ClaudeAdapter.snapshot", lambda _self: Snapshot(provider="claude", label="Claude", tokens=7))

    snapshots = collect(["codex", "claude"])

    assert len(snapshots) == 2
    assert snapshots[0].error == "适配器异常：RuntimeError"
    assert snapshots[1].tokens == 7
