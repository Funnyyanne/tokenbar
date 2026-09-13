from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict

from . import __version__
from .adapters import ClaudeAdapter, CodexAdapter, KimiAdapter
from .models import Snapshot
from .render import clear_screen, render_line
from .integrations import integration_help, render_stdin_statusline


def make_adapters(names: list[str]):
    registry = {"codex": CodexAdapter, "claude": ClaudeAdapter, "kimi": KimiAdapter}
    for name in names:
        adapter = registry.get(name)
        if adapter is None:
            raise ValueError(f"不支持的 provider：{name}")
        yield adapter()


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
        choices=("status", "watch", "integrate", "claude-statusline", "kimi-statusline"),
        default="status",
    )
    parser.add_argument("target", nargs="?", help="integrate 的目标：claude、kimi、codex")
    parser.add_argument("--providers", default="codex,claude,kimi", help="逗号分隔：codex,claude,kimi")
    parser.add_argument("--interval", type=float, default=10.0, help="watch 刷新秒数，最小 2 秒")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    if args.command in {"claude-statusline", "kimi-statusline"}:
        return render_stdin_statusline("claude" if args.command.startswith("claude") else "kimi", "Claude" if args.command.startswith("claude") else "Kimi")
    if args.command == "integrate":
        if args.target not in {"claude", "kimi", "codex"}:
            parser.error("integrate 需要目标：claude、kimi 或 codex")
        print(integration_help(args.target))
        return 0
    names = [name.strip().lower() for name in args.providers.split(",") if name.strip()]
    if args.interval < 2:
        parser.error("--interval 不能小于 2 秒")
    use_color = sys.stdout.isatty() and not args.no_color and "NO_COLOR" not in __import__("os").environ
    try:
        while True:
            snapshots = collect(names)
            if args.as_json:
                print(json.dumps([snapshot_dict(snapshot) for snapshot in snapshots], ensure_ascii=False), flush=True)
            elif args.command == "watch":
                if use_color:
                    clear_screen()
                print(render_line(snapshots, color=use_color), flush=True)
            else:
                print(render_line(snapshots, color=use_color))
            if args.command != "watch":
                return 0 if any(not snapshot.error for snapshot in snapshots) else 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
