from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .base import Adapter
from .common import iter_json_objects, newest_files, usage_from_object
from .jsonl import JsonlAdapter
from .sqlite import SqliteAdapter, SqliteSchema
from ..models import Snapshot, as_int


def _json_lines_tail(path: Path, max_bytes: int = 8 * 1024 * 1024):
    with path.open("rb") as handle:
        handle.seek(max(0, path.stat().st_size - max_bytes))
        if handle.tell():
            handle.readline()
        for raw in handle:
            try:
                yield json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue


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


class ZCodeAdapter(Adapter):
    """Read ZCode's model_usage ledger without double-counting cache breakdowns."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.provider, self.label, self.maturity = "zcode", "ZCode", "experimental"
        self.roots = roots or [Path.home() / ".zcode" / "cli" / "db", Path.home() / ".zcode"]

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("db.sqlite", "*.db", "*.sqlite")):
            db: sqlite3.Connection | None = None
            try:
                db = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
                db.execute("PRAGMA query_only=ON")
                rows = db.execute('''SELECT input_tokens, output_tokens,
                    cache_creation_input_tokens, cache_read_input_tokens,
                    provider_total_tokens, computed_total_tokens, model_id
                    FROM model_usage''').fetchall()
            except sqlite3.Error:
                continue
            finally:
                if db is not None:
                    db.close()
            total = input_total = output_total = 0
            model = None
            for input_value, output_value, cache_creation, cache_read, provider_total, computed_total, candidate_model in rows:
                input_value = as_int(input_value) or 0
                output_value = as_int(output_value) or 0
                cache = (as_int(cache_creation) or 0) + (as_int(cache_read) or 0)
                row_total = as_int(provider_total) or as_int(computed_total) or input_value + output_value
                with_cache = input_value + cache + output_value
                without_cache = input_value + output_value
                input_total += input_value + cache if abs(row_total - with_cache) < abs(row_total - without_cache) else (input_value or cache)
                output_total += output_value
                total += row_total
                if isinstance(candidate_model, str) and candidate_model:
                    model = candidate_model
            if total:
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity, model=model, tokens=total, input_tokens=input_total, output_tokens=output_total, source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到 ZCode model_usage token 数据", ", ".join(map(str, self.roots)), maturity=self.maturity)


class JsonUsageAdapter(JsonlAdapter):
    """Provider-specific JSON/JSONL usage reader with an allowlisted source."""

    def __init__(self, provider: str, label: str, roots: list[Path], patterns: tuple[str, ...], *, maturity: str = "experimental") -> None:
        super().__init__(provider, label, roots, patterns=patterns, maturity=maturity)


class RooAdapter(JsonUsageAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("roo", "Roo", roots or [
            Path.home() / ".roo",
            Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline",
            Path.home() / ".config" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline",
        ], ("history_item.json",), maturity="experimental")


class GeminiAdapter(Adapter):
    """Read Gemini CLI's documented saved-session token summaries."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.provider, self.label, self.maturity = "gemini", "Gemini", "experimental"
        self.roots = roots or [Path.home() / ".gemini" / "tmp"]

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("session-*.json", "session-*.jsonl")):
            try:
                if path.stat().st_size > 16 * 1024 * 1024:
                    continue
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            messages = value.get("messages") if isinstance(value, dict) else None
            if not isinstance(messages, list):
                continue
            total = input_tokens = output_tokens = 0
            model = None
            for message in messages:
                if not isinstance(message, dict) or message.get("type") != "gemini":
                    continue
                usage = message.get("tokens")
                if not isinstance(usage, dict):
                    continue
                input_tokens += as_int(usage.get("input")) or 0
                output_tokens += (as_int(usage.get("output")) or 0) + (as_int(usage.get("thoughts")) or 0)
                total += as_int(usage.get("total")) or 0
                if isinstance(message.get("model"), str):
                    model = message["model"]
            if total or input_tokens or output_tokens:
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity, model=model, tokens=total or input_tokens + output_tokens, input_tokens=input_tokens, output_tokens=output_tokens, source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到 Gemini CLI 保存会话中的 token 统计", ", ".join(map(str, self.roots)), maturity=self.maturity)


class PiSessionAdapter(Adapter):
    """Read pi/OMP assistant-message usage without traversing message content."""

    def __init__(self, provider: str, label: str, roots: list[Path]) -> None:
        self.provider, self.label, self.roots = provider, label, roots
        self.maturity = "experimental"

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("*.jsonl",)):
            totals = {"input": 0, "output": 0, "cache": 0}
            model = None
            try:
                for entry in _json_lines_tail(path):
                    message = entry.get("message") if isinstance(entry, dict) and entry.get("type") == "message" else None
                    if not isinstance(message, dict) or message.get("role") != "assistant":
                        continue
                    usage = message.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    totals["input"] += as_int(usage.get("input")) or 0
                    totals["output"] += as_int(usage.get("output")) or 0
                    totals["cache"] += (as_int(usage.get("cacheRead")) or 0) + (as_int(usage.get("cacheWrite")) or 0)
                    if isinstance(message.get("model"), str):
                        model = message["model"]
            except (OSError, UnicodeDecodeError):
                continue
            total = sum(totals.values())
            if total:
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity, model=model, tokens=total, input_tokens=totals["input"] + totals["cache"], output_tokens=totals["output"], source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到 assistant message usage", ", ".join(map(str, self.roots)), maturity=self.maturity)


class PiAdapter(PiSessionAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("pi", "Pi", roots or [Path.home() / ".pi" / "agent" / "sessions"])


class OmpAdapter(PiSessionAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("omp", "OMP", roots or [Path.home() / ".omp" / "agent" / "sessions"])


def _otel_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in ("intValue", "doubleValue", "stringValue", "value"):
        if key in value:
            return value[key]
    return value


class CopilotAdapter(Adapter):
    """Read GitHub Copilot CLI chat spans from its official OTel JSONL export."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.provider, self.label, self.maturity = "copilot", "Copilot", "experimental"
        configured = os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH")
        self.explicit_file = Path(configured).expanduser() if configured else None
        self.roots = roots or [Path.home() / ".copilot" / "otel"]

    def snapshot(self) -> Snapshot:
        files = []
        if self.explicit_file and self.explicit_file.is_file():
            files.append(self.explicit_file)
        files.extend(path for path in newest_files(self.roots, ("*.jsonl",)) if path not in files)
        for path in files:
            totals = {"input": 0, "output": 0}
            model = None
            seen: set[str] = set()
            try:
                for record in _json_lines_tail(path):
                    if not isinstance(record, dict):
                        continue
                    attrs = record.get("attributes")
                    if not isinstance(attrs, dict):
                        continue
                    operation = _otel_value(attrs.get("gen_ai.operation.name"))
                    if operation != "chat":
                        continue
                    span_id = str(record.get("spanId") or record.get("span_id") or "")
                    if span_id and span_id in seen:
                        continue
                    if span_id:
                        seen.add(span_id)
                    input_value = as_int(_otel_value(attrs.get("gen_ai.usage.input_tokens"))) or 0
                    cache_read = as_int(_otel_value(attrs.get("gen_ai.usage.cache_read.input_tokens", attrs.get("gen_ai.usage.cache_read_input_tokens")))) or 0
                    cache_creation = as_int(_otel_value(attrs.get("gen_ai.usage.cache_creation.input_tokens", attrs.get("gen_ai.usage.cache_creation_input_tokens")))) or 0
                    totals["input"] += max(input_value, cache_read) + cache_creation
                    totals["output"] += as_int(_otel_value(attrs.get("gen_ai.usage.output_tokens"))) or 0
                    candidate = _otel_value(attrs.get("gen_ai.response.model", attrs.get("gen_ai.request.model")))
                    if isinstance(candidate, str) and candidate:
                        model = candidate
            except (OSError, UnicodeDecodeError):
                continue
            total = sum(totals.values())
            if total:
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity, model=model, tokens=total, input_tokens=totals["input"], output_tokens=totals["output"], source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到 Copilot OTel chat span；请设置 COPILOT_OTEL_FILE_EXPORTER_PATH", ", ".join(map(str, self.roots)), maturity=self.maturity)


class ZedAdapter(Adapter):
    """Read JSON-backed Zed thread rows; compressed rows are reported unavailable."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.provider, self.label, self.maturity = "zed", "Zed", "experimental"
        self.roots = roots or [Path.home() / ".local" / "share" / "zed", Path.home() / "Library" / "Application Support" / "Zed"]

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("threads.db", "*.db")):
            db: sqlite3.Connection | None = None
            try:
                db = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
                db.execute("PRAGMA query_only=ON")
                columns = {row[1] for row in db.execute('PRAGMA table_info("threads")')}
                order = " ORDER BY updated_at DESC" if "updated_at" in columns else ""
                rows = db.execute(f"SELECT data, data_type FROM threads{order}")
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


class JsonPathSqliteAdapter(Adapter):
    """Use SQLite JSON extraction so prompt/response columns never leave the DB."""

    def __init__(self, provider: str, label: str, roots: list[Path], table: str, column: str, json_root: str, patterns: tuple[str, ...] = ("*.db", "*.sqlite")) -> None:
        self.provider, self.label, self.roots = provider, label, roots
        self.table, self.column, self.json_root, self.patterns = table, column, json_root, patterns
        self.maturity = "experimental"

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, self.patterns):
            db: sqlite3.Connection | None = None
            try:
                db = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
                db.execute("PRAGMA query_only=ON")
                prefix = self.json_root.rstrip(".")
                rows = db.execute(
                    f'''SELECT
                        json_extract("{self.column}", '{prefix}.input_tokens'),
                        json_extract("{self.column}", '{prefix}.output_tokens'),
                        json_extract("{self.column}", '{prefix}.prompt_tokens'),
                        json_extract("{self.column}", '{prefix}.completion_tokens'),
                        json_extract("{self.column}", '{prefix}.cache_read_tokens'),
                        json_extract("{self.column}", '{prefix}.cache_creation_tokens'),
                        json_extract("{self.column}", '$.metadata.generation_model')
                    FROM "{self.table}"
                    WHERE json_valid("{self.column}")'''
                ).fetchall()
            except sqlite3.Error:
                continue
            finally:
                if db is not None:
                    db.close()
            totals = {"input": 0, "output": 0, "cache": 0}
            model = None
            for input_value, output_value, prompt_value, completion_value, cache_read, cache_creation, candidate_model in rows:
                totals["input"] += as_int(input_value) or as_int(prompt_value) or 0
                totals["output"] += as_int(output_value) or as_int(completion_value) or 0
                totals["cache"] += (as_int(cache_read) or 0) + (as_int(cache_creation) or 0)
                if isinstance(candidate_model, str) and candidate_model:
                    model = candidate_model
            total = sum(totals.values())
            if total:
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity, model=model, tokens=total, input_tokens=totals["input"] + totals["cache"], output_tokens=totals["output"], source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到可识别 token 字段", ", ".join(map(str, self.roots)), maturity=self.maturity)


class DevinAdapter(JsonPathSqliteAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("devin", "Devin", roots or [Path.home() / ".local" / "share" / "devin", Path.home() / "Library" / "Application Support" / "devin"], "message_nodes", "chat_message", "$.metadata.metrics", ("sessions.db", "*.db"))


class AnythingLLMAdapter(JsonPathSqliteAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("anythingllm", "AnythingLLM", roots or [Path.home() / "Library" / "Application Support" / "anythingllm-desktop", Path.home() / ".anythingllm"], "workspace_chats", "response", "$.metrics", ("*.db", "*.sqlite"))
