from __future__ import annotations

import json
import shlex
import sys
from typing import Any

from .models import RateWindow, Snapshot, as_float, as_int
from .render import render_snapshot


def _read_stdin_json() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _percent(value: Any) -> float | None:
    return as_float(value)


def snapshot_from_statusline(provider: str, label: str, data: dict[str, Any]) -> Snapshot:
    model = data.get("model")
    if isinstance(model, dict):
        model = model.get("display_name") or model.get("id")
    context = data.get("context_window") or {}
    usage = context.get("current_usage") or {}
    context_used = as_int(usage.get("input_tokens"))
    context_window = as_int(context.get("context_window_size"))
    if context.get("used_percentage") is not None and context_window:
        context_used = round(context_window * float(context["used_percentage"]) / 100)
    limits = data.get("rate_limits") or {}
    windows: list[RateWindow] = []
    for key, title in (("five_hour", "5h"), ("seven_day", "7d")):
        item = limits.get(key)
        if isinstance(item, dict):
            windows.append(RateWindow(title, _percent(item.get("used_percentage")), as_float(item.get("resets_at"))))
    current = usage.get("input_tokens")
    output = usage.get("output_tokens")
    return Snapshot(
        provider=provider,
        label=label,
        model=model if isinstance(model, str) else None,
        tokens=(as_int(current) or 0) + (as_int(output) or 0) if current is not None or output is not None else None,
        input_tokens=as_int(current),
        output_tokens=as_int(output),
        context_used=context_used,
        context_window=context_window,
        rate_limits=windows,
    )


def render_stdin_statusline(provider: str, label: str) -> int:
    data = _read_stdin_json()
    snapshot = snapshot_from_statusline(provider, label, data)
    print(render_snapshot(snapshot, color=True), flush=True)
    return 0


def integration_help(target: str, executable: str | None = None) -> str:
    executable = executable or "ai-cli-statusline"
    command = shlex.quote(executable)
    if target == "claude":
        return """Claude Code 原生 statusLine 配置（写入 ~/.claude/settings.json）：
{
  \"statusLine\": {
    \"type\": \"command\",
    \"command\": %s,
    \"refreshInterval\": 5
  }
}

命令：%s claude-statusline
""" % (json.dumps(f"{executable} claude-statusline"), command)
    if target == "kimi":
        return """Kimi Code 原生 tui.toml 配置（写入 ~/.kimi-code/tui.toml，旧版可能是 ~/.kimi/tui.toml）：
[status_line]
command = %s

命令：%s kimi-statusline
然后在 Kimi 中执行 /reload-tui。
""" % (json.dumps(f"{executable} kimi-statusline"), command)
    if target == "codex":
        return """Codex 当前没有“外部命令 status_line”扩展点；原生底部栏由 tui.status_line 项目绘制。
保留 ~/.codex/config.toml 的 tui.status_line（含 used-tokens、context-remaining、five-hour-limit、weekly-limit）。
Hook 需要由 Codex 的 hooks.json 调用一个“读 stdin、输出 systemMessage”的脚本；本项目提供的 Stop Hook 示例见项目文档。

旁路持续刷新：%s watch --providers codex,claude,kimi --interval 10
""" % (command, command)
    raise ValueError(f"不支持的集成目标：{target}")
