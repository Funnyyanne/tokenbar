from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .base import Adapter
from .common import iter_json_objects, newest_files, usage_from_object
from .jsonl import JsonlAdapter
from .sqlite import SqliteAdapter, SqliteSchema
from ..models import Snapshot, as_int


class GooseAdapter(SqliteAdapter):
    """Read Goose's explicit ``usage_ledger`` table."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(
            "goose", roots or [Path.home() / ".local" / "share" / "goose"],
            schemas=(SqliteSchema(
                table="usage_ledger",
                input_columns=("input_tokens",),
                output_columns=("output_tokens",),
                cache_columns=("cache_read_tokens", "cache_write_tokens"),
                total_columns=("total_tokens",),
                model_column="model",
            ),),
            patterns=("sessions.db", "*.db", "*.sqlite"), maturity="experimental",
        )
        self.label = "Goose"


class KiloAdapter(SqliteAdapter):
    """Kilo stores usage in the OpenCode-compatible session database."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(
            "kilo", roots or [Path.home() / ".local" / "share" / "kilo"],
            schemas=(SqliteSchema(
                table="session", input_columns=("tokens_input",),
                output_columns=("tokens_output", "tokens_reasoning"),
                cache_columns=("tokens_cache_read", "tokens_cache_write"),
                model_column="model",
            ),), patterns=("kilo.db", "db.sqlite", "*.db", "*.sqlite"),
            maturity="experimental",
        )
        self.label = "Kilo"


class MimoAdapter(KiloAdapter):
    """MiMoCode's local store follows the OpenCode session schema."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(roots or [Path.home() / ".local" / "share" / "mimocode"])
        self.provider, self.label = "mimo", "MiMo"


class ZCodeAdapter(SqliteAdapter):
    """Read ZCode's explicit model_usage ledger."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(
            "zcode", roots or [Path.home() / ".zcode" / "cli" / "db", Path.home() / ".zcode"],
            schemas=(SqliteSchema(
                table="model_usage", input_columns=("input_tokens",),
                output_columns=("output_tokens", "reasoning_tokens"),
                cache_columns=("cache_creation_input_tokens", "cache_read_input_tokens"),
                total_columns=("computed_total_tokens",), model_column="model",
            ),), patterns=("db.sqlite", "*.db", "*.sqlite"), maturity="experimental",
        )
        self.label = "ZCode"


class JsonUsageAdapter(JsonlAdapter):
    """Provider-specific JSON/JSONL usage reader with an allowlisted source."""

    def __init__(self, provider: str, label: str, roots: list[Path], patterns: tuple[str, ...], *, maturity: str = "experimental") -> None:
        super().__init__(provider, label, roots, patterns=patterns, maturity=maturity)


class RooAdapter(JsonUsageAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("roo", "Roo", roots or [Path.home() / ".roo", Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage"], ("history_item.json",), maturity="experimental")


class LmStudioAdapter(JsonUsageAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("lmstudio", "LM Studio", roots or [Path.home() / ".lmstudio" / "server-logs"], ("*.jsonl", "*.json"), maturity="experimental")


class CopilotAdapter(JsonUsageAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("copilot", "Copilot", roots or [Path.home() / ".copilot"], ("*.jsonl", "*.json"), maturity="experimental")


class QoderAdapter(JsonUsageAdapter):
    """Best-effort reader for explicit usage objects in Qoder transcripts.

    Qoder's public CLI reports credits rather than a stable local token schema;
    this reader only accepts transcript objects that contain standard usage keys.
    """

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("qoder", "Qoder", roots or [Path.home() / ".qoder" / "projects", Path.home() / ".qoderwork" / "projects", Path.home() / "Library" / "Application Support" / "Qoder"], ("*.jsonl", "*.json"), maturity="experimental")


class ZedAdapter(Adapter):
    """Read JSON-backed Zed thread rows; compressed rows are reported unavailable."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.provider, self.label, self.maturity = "zed", "Zed", "experimental"
        self.roots = roots or [Path.home() / ".local" / "share" / "zed", Path.home() / "Library" / "Application Support" / "Zed"]

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("threads.db", "*.db")):
            try:
                db = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
                db.execute("PRAGMA query_only=ON")
                rows = db.execute("SELECT data, data_type FROM threads").fetchall()
                totals = {"input": 0, "output": 0}
                model = None
                for raw, data_type in rows:
                    if str(data_type).lower() not in {"json", ""} or not isinstance(raw, (str, bytes)):
                        continue
                    try:
                        value = json.loads(raw)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    for obj in iter_json_objects(value):
                        usage = usage_from_object(obj)
                        if usage:
                            totals["input"] += usage["input"] + usage["cache"]
                            totals["output"] += usage["output"]
                        candidate = obj.get("model")
                        if isinstance(candidate, str):
                            model = candidate
                db.close()
            except sqlite3.Error:
                continue
            total = totals["input"] + totals["output"]
            if total:
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity, model=model, tokens=total, input_tokens=totals["input"], output_tokens=totals["output"], source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到可识别的 JSON token 用量（压缩线程暂不读取）", ", ".join(map(str, self.roots)), maturity=self.maturity)


class JsonMetricSqliteAdapter(Adapter):
    """Read token metrics only from an allowlisted JSON column in a known table."""

    def __init__(self, provider: str, label: str, roots: list[Path], table: str, column: str, patterns: tuple[str, ...] = ("*.db", "*.sqlite")) -> None:
        self.provider, self.label, self.roots, self.table, self.column, self.patterns = provider, label, roots, table, column, patterns
        self.maturity = "experimental"

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, self.patterns):
            try:
                db = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
                db.execute("PRAGMA query_only=ON")
                rows = db.execute(f'SELECT "{self.column}" FROM "{self.table}"').fetchall()
            except sqlite3.Error:
                continue
            finally:
                try: db.close()
                except UnboundLocalError: pass
            totals = {"input": 0, "output": 0, "cache": 0}
            model = None
            for (raw,) in rows:
                try: value = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                except (TypeError, json.JSONDecodeError): continue
                for obj in iter_json_objects(value):
                    usage = usage_from_object(obj)
                    if usage:
                        for key in totals: totals[key] += usage[key]
                    if isinstance(obj.get("model"), str): model = obj["model"]
            total = sum(totals.values())
            if total:
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity, model=model, tokens=total, input_tokens=totals["input"] + totals["cache"], output_tokens=totals["output"], source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到可识别 token 字段", ", ".join(map(str, self.roots)), maturity=self.maturity)


class DevinAdapter(JsonMetricSqliteAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("devin", "Devin", roots or [Path.home() / ".local" / "share" / "devin", Path.home() / "Library" / "Application Support" / "devin"], "message_nodes", "chat_message", ("sessions.db", "*.db"))


class AnythingLLMAdapter(JsonMetricSqliteAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("anythingllm", "AnythingLLM", roots or [Path.home() / "Library" / "Application Support" / "anythingllm-desktop", Path.home() / ".anythingllm"], "workspace_chats", "response", ("*.db", "*.sqlite"))
