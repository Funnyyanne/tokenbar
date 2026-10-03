from __future__ import annotations

import json
import os
import select
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "posix", reason="PTY terminal check requires POSIX")
@pytest.mark.parametrize("exit_signal", [signal.SIGINT, signal.SIGTERM], ids=["sigint", "sigterm"])
@pytest.mark.parametrize("options,term,no_color,screen", [
    (["--no-color"], "xterm-256color", False, True),
    ([], "xterm-256color", True, True),
    ([], "dumb", False, False),
    (["--json"], "xterm-256color", False, False),
])
def test_watch_pty_progress_refresh_and_exit(tmp_path, options, term, no_color, screen, exit_signal):
    import fcntl
    import pty
    import termios

    source = tmp_path / "sessions"
    source.mkdir()
    log = source / "fixture.jsonl"
    log.write_text(json.dumps({"usage": {"input_tokens": 10, "output_tokens": 2}, "context_used": 25, "context_window": 100}) + "\n")
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 40, 0, 0))
    env = {**os.environ, "TERM": term, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
           "AI_CLI_STATUSLINE_SOURCES": json.dumps({"fixture": [str(source)]}),
           "AI_CLI_STATUSLINE_HOME": str(tmp_path / "cache")}
    env.pop("NO_COLOR", None)
    env.pop("COLUMNS", None)
    if no_color:
        env["NO_COLOR"] = "1"
    process = subprocess.Popen([sys.executable, "-m", "ai_cli_statusline", "watch", "--providers", "fixture", "--interval", "2", *options],
                               stdin=subprocess.DEVNULL, stdout=slave, stderr=subprocess.PIPE, env=env)
    # Keep a slave descriptor until output is drained: macOS can discard
    # pending PTY bytes when the final slave descriptor closes.
    captured = bytearray()

    def read_until(marker: bytes) -> None:
        deadline = time.monotonic() + 6
        while marker not in captured and time.monotonic() < deadline:
            if select.select([master], [], [], 0.2)[0]:
                try:
                    captured.extend(os.read(master, 65536))
                except OSError:
                    break
        assert marker in captured, captured.decode(errors="replace")

    try:
        read_until(b'"context_used": 25' if "--json" in options else b"25%")
        with log.open("a") as handle:
            handle.write(json.dumps({"usage": {"input_tokens": 10, "output_tokens": 2}, "context_used": 75, "context_window": 100}) + "\n")
        read_until(b'"context_used": 75' if "--json" in options else b"75%")
        process.send_signal(exit_signal)
        if screen:
            read_until(b"\x1b[?25h\x1b[?1049l")
        process.wait(timeout=5)
        while select.select([master], [], [], 0.2)[0]:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured.extend(chunk)
        assert process.returncode == (0 if exit_signal == signal.SIGINT else 128 + signal.SIGTERM)
        assert process.stderr is not None and process.stderr.read() == b""
        if screen:
            assert captured.count(b"\x1b[2J\x1b[H") >= 2
            assert captured.startswith(b"\x1b[?1049h\x1b[?25l")
            assert captured.endswith(b"\x1b[?25h\x1b[?1049l")
            assert b"\x1b[38;" not in captured
        else:
            assert b"\x1b" not in captured
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stderr is not None:
            process.stderr.close()
        os.close(slave)
        os.close(master)


@pytest.mark.skipif(os.name != "posix", reason="PTY terminal check requires POSIX")
@pytest.mark.parametrize("providers", ["not-a-provider", "fixture,not-a-provider"])
def test_invalid_provider_error_stays_on_original_screen(tmp_path, providers):
    import pty

    master, slave = pty.openpty()
    env = {**os.environ, "TERM": "xterm-256color",
           "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
           "AI_CLI_STATUSLINE_SOURCES": json.dumps({"fixture": [str(tmp_path)]}),
           "AI_CLI_STATUSLINE_HOME": str(tmp_path / "cache")}
    process = subprocess.Popen([sys.executable, "-m", "ai_cli_statusline", "watch", "--providers", providers, "--no-color"],
                               stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, env=env)
    captured = bytearray()
    try:
        process.wait(timeout=5)
        while select.select([master], [], [], 0.2)[0]:
            captured.extend(os.read(master, 65536))
        assert process.returncode == 2
        assert "不支持的 provider：not-a-provider".encode() in captured
        assert b"\x1b" not in captured
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        os.close(slave)
        os.close(master)
