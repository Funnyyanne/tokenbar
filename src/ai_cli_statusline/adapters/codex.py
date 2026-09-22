from __future__ import annotations

import json
import os
import select
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from .base import Adapter
from ..models import RateWindow, Snapshot, as_float, as_int


class CodexAdapter(Adapter):
    provider = "codex"
    label = "Codex"

    def __init__(self, codex_home: Path | None = None, timeout: float = 8.0) -> None:
        self.home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.timeout = timeout

    def _rpc(self, method: str, request_id: int, params: Any = None) -> dict[str, Any]:
        binary = shutil.which("codex")
        if not binary:
            raise RuntimeError("未找到 codex CLI")
        process = subprocess.Popen(
            [binary, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        try:
            deadline = time.monotonic() + self.timeout

            def read_line() -> str:
                assert process.stdout is not None
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                    raise RuntimeError(f"Codex {method} 查询超时")
                line = process.stdout.readline()
                if not line:
                    raise RuntimeError("Codex app-server 提前退出")
                return line

            def send(payload: dict[str, Any]) -> None:
                assert process.stdin is not None
                process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
                process.stdin.flush()

            send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "ai-cli-statusline", "title": "AI CLI Statusline", "version": "0.1.0"}, "capabilities": None}})
            response: dict[str, Any] | None = None
            while True:
                line = read_line()
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict) and message.get("id") == 1:
                    response = message
                    break
            if response is None or "error" in response:
                raise RuntimeError("Codex app-server 初始化失败")
            send({"method": "initialized"})
            send({"id": request_id, "method": method, "params": params} if params is not None else {"id": request_id, "method": method})
            while True:
                line = read_line()
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(message, dict) and message.get("id") == request_id:
                    if "error" in message:
                        raise RuntimeError(str(message["error"]))
                    result = message.get("result")
                    return result if isinstance(result, dict) else {}
        finally:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()

    def _thread(self) -> tuple[int | None, int | None, str | None]:
        def mtime(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:
                return 0.0

        candidates = sorted(self.home.glob("state_*.sqlite"), key=mtime, reverse=True)
        if not candidates:
            return None, None, None
        for path in candidates:
            connection: sqlite3.Connection | None = None
            try:
                connection = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
                connection.execute("PRAGMA query_only=ON")
                row = connection.execute("SELECT tokens_used, COALESCE(updated_at_ms, updated_at * 1000), model FROM threads WHERE archived = 0 AND thread_source = 'user' ORDER BY COALESCE(updated_at_ms, updated_at * 1000) DESC LIMIT 1").fetchone()
                if row:
                    return as_int(row[0]), as_int(row[1]), row[2] if isinstance(row[2], str) else None
            except sqlite3.Error:
                continue
            finally:
                if connection is not None:
                    connection.close()
        return None, None, None

    @staticmethod
    def _windows(value: dict[str, Any]) -> list[RateWindow]:
        limits = value.get("rateLimitsByLimitId")
        if isinstance(limits, dict) and isinstance(limits.get("codex"), dict):
            value = limits["codex"]
        else:
            value = value.get("rateLimits", value) if isinstance(value.get("rateLimits", value), dict) else value
        result: list[RateWindow] = []
        for key, label in (("primary", "5h"), ("secondary", "7d")):
            window = value.get(key)
            if not isinstance(window, dict):
                continue
            used = window.get("usedPercent", window.get("used_percent"))
            result.append(RateWindow(label, as_float(used), as_float(window.get("resetsAt", window.get("resets_at")))))
        return result

    def snapshot(self) -> Snapshot:
        tokens, _updated, model = self._thread()
        rate_error: str | None = None
        rate: dict[str, Any] = {}
        try:
            rate = self._rpc("account/rateLimits/read", 2)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            rate_error = str(exc)
        if tokens is None and rate_error:
            return Snapshot.unavailable(self.provider, self.label, rate_error, str(self.home))
        return Snapshot(
            provider=self.provider,
            label=self.label,
            model=model,
            tokens=tokens,
            rate_limits=self._windows(rate),
            source=str(self.home),
            error=f"额度不可用：{rate_error}" if rate_error else None,
        )
