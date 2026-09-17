from __future__ import annotations

import io

from ai_cli_statusline.integrations import snapshot_from_statusline
from ai_cli_statusline.integrations import setup_claude, setup_kimi
from ai_cli_statusline.integrations import _read_stdin_json


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
