from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

from .models import RateWindow, Snapshot, as_float, as_int
from .render import render_snapshot
from .cache import write_snapshot


def _read_stdin_json() -> dict[str, Any]:
    # Native status-line integrations receive JSON from the host CLI. When a
    # user runs the helper manually in an interactive terminal, do not block
    # waiting for input forever.
    if sys.stdin.isatty():
        return {}
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
    if snapshot.model or snapshot.tokens is not None or snapshot.context_percent is not None or snapshot.rate_limits:
        write_snapshot(snapshot)
    use_color = "NO_COLOR" not in os.environ
    print(render_snapshot(snapshot, color=use_color), flush=True)
    return 0


def integration_help(target: str, executable: str | None = None) -> str:
    executable = executable or "tokenbar"
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


def _command(executable: str | None = None) -> str:
    if executable:
        return executable
    installed = shutil.which("tokenbar") or shutil.which("ai-cli-statusline")
    return installed or f"{shlex.quote(sys.executable)} -m ai_cli_statusline"


def setup_claude(force: bool = False, executable: str | None = None) -> Path:
    path = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).expanduser() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Claude settings.json 不是有效 JSON：{path}") from exc
    if not isinstance(settings, dict):
        raise RuntimeError(f"Claude settings.json 顶层不是对象：{path}")
    if "statusLine" in settings and not force:
        raise RuntimeError(f"已存在 statusLine，未覆盖：{path}；如需覆盖请加 --force")
    if path.exists():
        path.with_suffix(path.suffix + ".bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    settings["statusLine"] = {"type": "command", "command": f"{_command(executable)} claude-statusline", "refreshInterval": 5}
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def setup_kimi(force: bool = False, executable: str | None = None) -> Path:
    path = Path(os.environ.get("KIMI_CODE_HOME", Path.home() / ".kimi-code")).expanduser() / "tui.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    has_status_line = any(
        line.strip() == "[status_line]"
        for line in content.splitlines()
        if not line.strip().startswith("#")
    )
    if has_status_line and not force:
        raise RuntimeError(f"已存在 [status_line]，未覆盖：{path}；如需覆盖请加 --force")
    if path.exists():
        path.with_suffix(path.suffix + ".bak").write_text(content, encoding="utf-8")
    command_value = f"{_command(executable)} kimi-statusline"
    command = f"command = {json.dumps(command_value)}"
    if has_status_line:
        lines: list[str | None] = content.splitlines()
        in_status = False
        replaced = False
        insert_at: int | None = None
        for index, line in enumerate(lines):
            assert line is not None
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if in_status and not replaced and insert_at is None:
                    insert_at = index
                in_status = stripped == "[status_line]"
            elif in_status and re.match(r"^\s*command\s*=", line):
                if replaced:
                    lines[index] = None  # 旧的 setup --force 可能留下重复 command，一并删除
                else:
                    lines[index] = command
                    replaced = True
        kept = [line for line in lines if line is not None]
        if not replaced:
            target = len(kept) if insert_at is None else insert_at
            while target > 0 and not kept[target - 1].strip():
                target -= 1
            kept.insert(target, command)
        content = "\n".join(kept) + "\n"
    else:
        content = content.rstrip() + ("\n\n" if content.strip() else "") + "[status_line]\n" + command + "\n"
    path.write_text(content, encoding="utf-8")
    return path
