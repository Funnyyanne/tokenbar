from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .base import Adapter
from .common import iter_json_objects, newest_files, usage_from_object
from .jsonl import JsonlAdapter
from .sqlite import SqliteAdapter, SqliteSchema
from .opencode import OpenCodeAdapter
from .terminal import PiMetadataAdapter, PiTreeAdapter
from .native import DevinAdapter, read_copilot_store
from .metadata import json_metadata, valid_token_count
from .zcode import ZCodeAdapter
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


class KiloAdapter(OpenCodeAdapter):
    """Kilo stores usage in the OpenCode-compatible session database."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(roots or [Path.home() / ".local" / "share" / "kilo"])
        self.provider, self.maturity = "kilo", "experimental"
        self.schemas = (SqliteSchema(
                table="session", input_columns=("tokens_input",),
                output_columns=("tokens_output", "tokens_reasoning"),
                cache_columns=("tokens_cache_read", "tokens_cache_write"),
                model_column="model",
            ),)
        self.patterns = ("kilo.db", "db.sqlite", "*.db", "*.sqlite")
        self.label = "Kilo"


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


class PiSessionAdapter(PiMetadataAdapter):
    """Read pi/OMP assistant-message usage without traversing message content."""

    def __init__(self, provider: str, label: str, roots: list[Path]) -> None:
        self.provider, self.label, self.roots = provider, label, roots
        self.maturity = "experimental"

class PiAdapter(PiSessionAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("pi", "Pi", roots or [Path.home() / ".pi" / "agent" / "sessions"])


class OmpAdapter(PiTreeAdapter):
    provider, label = "omp", "OMP"

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(roots if roots is not None else [Path.home() / ".omp" / "agent" / "sessions"])


class CopilotAdapter(Adapter):
    """Read the native assistant ledger, falling back to explicit OTel usage."""

    _attributes = {
        "operation": "gen_ai.operation.name", "response_id": "gen_ai.response.id",
        "model": "gen_ai.response.model", "request_model": "gen_ai.request.model",
        "input": "gen_ai.usage.input_tokens", "output": "gen_ai.usage.output_tokens",
        "write": "gen_ai.usage.cache_write.input_tokens",
        "creation": "gen_ai.usage.cache_creation.input_tokens",
        "write_alias": "gen_ai.usage.cache_write_input_tokens",
        "creation_alias": "gen_ai.usage.cache_creation_input_tokens",
    }

    def _records(self, path: Path):
        fields = {"type": "$.type", "name": "$.name", "trace": "$.traceId", "span": "$.spanId"}
        # Flat attributes and OTLP typed values share the same accounting rules.
        for key, attribute in self._attributes.items():
            base = '$.attributes."' + attribute + '"'
            for suffix in ("", "intValue", "doubleValue", "stringValue", "value"):
                fields[key + ":" + suffix] = base + ("." + suffix if suffix else "")
        for row in json_metadata(path, fields, types={"metrics_type": "$.scopeMetrics"}):
            if row["metrics_type"] is not None:
                continue
            for key in self._attributes:
                row[key] = next((row[key + ":" + suffix] for suffix in ("", "intValue", "doubleValue", "stringValue", "value")
                    if row[key + ":" + suffix] is not None), None)
            yield row

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.provider, self.label, self.maturity = "copilot", "Copilot", "experimental"
        configured = os.environ.get("COPILOT_OTEL_FILE_EXPORTER_PATH")
        self.explicit_file = Path(configured).expanduser() if configured else None
        self.roots = roots if roots is not None else [Path.home() / ".copilot", Path.home() / ".copilot-otel"]
        self.otel_roots = roots if roots is not None else [Path.home() / ".copilot" / "otel", Path.home() / ".copilot-otel"]

    def snapshot(self) -> Snapshot:
        native = read_copilot_store(self.roots)
        if native is not None:
            return native
        files = []
        if self.explicit_file and self.explicit_file.is_file():
            files.append(self.explicit_file)
        files.extend(path for path in newest_files(self.otel_roots, ("*.jsonl",)) if path not in files)
        for path in files:
            observations = {}
            try:
                for index, row in enumerate(self._records(path)):
                    cli_span = row["type"] == "span"
                    if row["operation"] != "chat" and not (cli_span and isinstance(row["name"], str) and row["name"].startswith("chat ")):
                        continue
                    input_value = valid_token_count(row["input"])
                    output_value = valid_token_count(row["output"])
                    if input_value is None or output_value is None:
                        continue
                    if not cli_span:
                        write = next((row[key] for key in ("write", "creation", "write_alias", "creation_alias") if row[key] is not None), 0)
                        write = valid_token_count(write)
                        if write is None:
                            continue
                        input_value += write
                    response_id = row["response_id"]
                    # LogRecords can share spanContext across independent responses.
                    if cli_span and row["trace"] and row["span"]:
                        key = ("span", row["trace"], row["span"])
                    elif isinstance(response_id, str) and response_id.strip():
                        key = ("response", response_id.strip())
                    else:
                        key = ("line", index)
                    model = row["model"] or row["request_model"]
                    observations[key] = (input_value, output_value, model if isinstance(model, str) else None)
            except (OSError, UnicodeDecodeError):
                continue
            input_total = sum(row[0] for row in observations.values())
            output_total = sum(row[1] for row in observations.values())
            total = input_total + output_total
            if total:
                models = [row[2] for row in observations.values() if row[2]]
                return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity,
                    model=models[-1] if models else None, tokens=total, input_tokens=input_total,
                    output_tokens=output_total, source=str(path))
        return Snapshot.unavailable(self.provider, self.label, "未找到 Copilot 原生或 OTel 用量元数据", ", ".join(map(str, self.roots)), maturity=self.maturity)


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


class AnythingLLMAdapter(JsonPathSqliteAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__("anythingllm", "AnythingLLM", roots or [Path.home() / "Library" / "Application Support" / "anythingllm-desktop", Path.home() / ".anythingllm"], "workspace_chats", "response", "$.metrics", ("*.db", "*.sqlite"))
