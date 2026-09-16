from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .adapters import ClaudeAdapter, CodexAdapter, GenericCliAdapter, KimiAdapter, SqliteAdapter
from .models import Snapshot
from .render import PROGRESS_STYLES, THEMES, clear_screen, get_theme, render_line
from .integrations import integration_help, render_stdin_statusline, setup_claude, setup_kimi


def make_adapters(names: list[str]):
    registry = {"codex": CodexAdapter, "claude": ClaudeAdapter, "kimi": KimiAdapter}
    built_in_roots = {
        "gemini": [Path.home() / ".gemini"],
        "antigravity": [Path.home() / ".gemini" / "antigravity", Path.home() / ".gemini" / "antigravity-cli"],
        "deepseek": [Path.home() / ".dsh" / "sessions"],
        "pi": [Path.home() / ".pi" / "agent" / "sessions"],
        "omp": [Path.home() / ".omp" / "agent" / "sessions"],
        "omo": [Path.home() / ".omo" / "agent" / "sessions"],
        "goose": [Path.home() / ".local" / "share" / "goose"],
        "craft": [Path.home() / ".craft-agent"],
        "reasonix": [Path.home() / ".reasonix"],
        "roo": [Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage"],
        "lmstudio": [Path.home() / ".lmstudio" / "server-logs"],
    }
    sqlite_roots = {
        "cursor": [Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage", Path.home() / ".config" / "Cursor" / "User" / "globalStorage"],
        "opencode": [Path.home() / ".local" / "share" / "opencode", Path.home() / ".config" / "opencode"],
        "copilot": [Path.home() / ".copilot"],
        "kilo": [Path.home() / ".local" / "share" / "kilo"],
        "zed": [Path.home() / ".local" / "share" / "zed"],
        "qoder": [Path.home() / "Library" / "Application Support" / "Qoder"],
        "anythingllm": [Path.home() / "Library" / "Application Support" / "anythingllm-desktop"],
        "devin": [Path.home() / ".local" / "share" / "devin"],
        "mimo": [Path.home() / ".local" / "share" / "mimocode"],
        "zcode": [Path.home() / ".zcode"],
    }
    custom_sources: dict[str, list[str]] = {}
    try:
        value = json.loads(os.environ.get("AI_CLI_STATUSLINE_SOURCES", "{}"))
        if isinstance(value, dict):
            custom_sources = {str(key).lower(): [str(item) for item in items] for key, items in value.items() if isinstance(items, list)}
    except json.JSONDecodeError:
        pass
    if "auto" in names:
        names = ["codex", "claude", "kimi", *built_in_roots, *sqlite_roots]
    for name in names:
        adapter = registry.get(name)
        if adapter is not None:
            yield adapter()
            continue
        roots = [Path(item).expanduser() for item in custom_sources.get(name, [])] or built_in_roots.get(name)
        if roots:
            yield GenericCliAdapter(name, roots)
            continue
        roots = sqlite_roots.get(name)
        if roots:
            yield SqliteAdapter(name, roots)
            continue
        raise ValueError(f"不支持的 provider：{name}；可用 AI_CLI_STATUSLINE_SOURCES 添加 JSONL 目录")


def snapshot_dict(snapshot: Snapshot) -> dict:
    value = asdict(snapshot)
    value["updated_at"] = snapshot.updated_at.isoformat()
    return value


def collect(names: list[str]) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    for adapter in make_adapters(names):
        try:
            snapshots.append(adapter.snapshot())
        except Exception as exc:  # adapters must never break the complete status line
            snapshots.append(Snapshot.unavailable(adapter.provider, adapter.label, f"适配器异常：{type(exc).__name__}"))
    return snapshots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI CLI token and rate-limit status bar")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("status", "watch", "integrate", "setup", "claude-statusline", "kimi-statusline"),
        default="status",
    )
    parser.add_argument("target", nargs="?", help="integrate 的目标：claude、kimi、codex")
    parser.add_argument("--providers", default="codex,claude,kimi", help="逗号分隔 provider，或使用 auto 扫描内置平台")
    parser.add_argument("--interval", type=float, default=10.0, help="watch 刷新秒数，最小 2 秒")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--theme", choices=sorted(THEMES), default=os.environ.get("AI_CLI_STATUSLINE_THEME", "catppuccin-mocha"), help="主题：catppuccin-mocha、nord、dracula、default")
    parser.add_argument("--progress-style", choices=sorted(PROGRESS_STYLES), default=os.environ.get("AI_CLI_STATUSLINE_PROGRESS_STYLE", "blocks"), help="进度样式：blocks、ascii、thin、dots")
    parser.add_argument("--force", action="store_true", help="setup 时覆盖已有 statusLine 配置并保留 .bak")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    if args.command in {"claude-statusline", "kimi-statusline"}:
        return render_stdin_statusline("claude" if args.command.startswith("claude") else "kimi", "Claude" if args.command.startswith("claude") else "Kimi")
    if args.command == "integrate":
        if args.target not in {"claude", "kimi", "codex"}:
            parser.error("integrate 需要目标：claude、kimi 或 codex")
        print(integration_help(args.target))
        return 0
    if args.command == "setup":
        if args.target not in {"claude", "kimi"}:
            parser.error("setup 需要目标：claude 或 kimi")
        try:
            path = setup_claude(args.force) if args.target == "claude" else setup_kimi(args.force)
        except RuntimeError as exc:
            parser.error(str(exc))
        print(f"已配置 {args.target}：{path}")
        return 0
    if args.target is not None:
        parser.error(f"{args.command} 不接受额外位置参数：{args.target}")
    names = [name.strip().lower() for name in args.providers.split(",") if name.strip()]
    if args.interval < 2:
        parser.error("--interval 不能小于 2 秒")
    use_color = sys.stdout.isatty() and not args.no_color and "NO_COLOR" not in __import__("os").environ
    theme = get_theme(args.theme)
    try:
        while True:
            snapshots = collect(names)
            if args.as_json:
                print(json.dumps([snapshot_dict(snapshot) for snapshot in snapshots], ensure_ascii=False), flush=True)
            elif args.command == "watch":
                if use_color:
                    clear_screen()
                print(render_line(snapshots, color=use_color, theme=theme, progress_style=args.progress_style), flush=True)
            else:
                print(render_line(snapshots, color=use_color, theme=theme, progress_style=args.progress_style))
            if args.command != "watch":
                return 0 if any(not snapshot.error for snapshot in snapshots) else 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
