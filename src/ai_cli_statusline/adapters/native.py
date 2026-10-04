from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .base import Adapter
from .common import newest_files
from .metadata import valid_token_count
from ..models import Snapshot


def read_copilot_store(roots: list[Path]) -> Snapshot | None:
    """Prefer Copilot's canonical assistant ledger to mirrored OTel spans."""
    empty = None
    for path in newest_files(roots, ("session-store.db",)):
        connection = None
        try:
            connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
            columns = {row[1] for row in connection.execute('PRAGMA table_info("assistant_usage_events")')}
            if not {"id", "input_tokens", "output_tokens"}.issubset(columns):
                continue
            model_column = '"model"' if "model" in columns else "NULL"
            observations = {}
            for identity, input_value, output_value, model in connection.execute(
                f"SELECT id, input_tokens, output_tokens, {model_column} FROM assistant_usage_events ORDER BY id"
            ):
                identity = valid_token_count(identity)
                input_value, output_value = valid_token_count(input_value), valid_token_count(output_value)
                if identity is None or input_value is None or output_value is None:
                    continue
                # Both parents already include cache/reasoning. No details blob is needed.
                observations[identity] = (input_value, output_value, model if isinstance(model, str) else None)
            input_total = sum(row[0] for row in observations.values())
            output_total = sum(row[1] for row in observations.values())
            if input_total + output_total:
                models = [row[2] for row in observations.values() if row[2]]
                return Snapshot(provider="copilot", label="Copilot", maturity="experimental",
                    tokens=input_total + output_total, input_tokens=input_total, output_tokens=output_total,
                    model=models[-1] if models else None, source=str(path))
            empty = Snapshot.unavailable("copilot", "Copilot", "Copilot 原生用量表暂无已完成 token 记录", str(path), maturity="experimental")
        except sqlite3.Error:
            continue
        finally:
            if connection is not None:
                connection.close()
    return empty


def _timestamp(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        result = parsed.timestamp()
        return result if result > 0 else None
    except (ValueError, OverflowError, OSError):
        return None


class DevinAdapter(Adapter):
    """Count finalized native requests once across forks/replays/compaction."""

    provider, label, maturity = "devin", "Devin", "experimental"

    def __init__(self, roots: list[Path] | None = None) -> None:
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")).expanduser()
        self.roots = roots if roots is not None else [data_home / "devin" / "cli"]

    def _read_database(self, path: Path) -> Snapshot | None:
        connection = None
        try:
            connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
            columns = {row[1] for row in connection.execute('PRAGMA table_info("message_nodes")')}
            if "chat_message" not in columns:
                return None
            row_id = "n.row_id" if "row_id" in columns else "n.rowid"
            session_id = "n.session_id" if "session_id" in columns else "NULL"
            session_columns = {row[1] for row in connection.execute('PRAGMA table_info("sessions")')}
            can_join = "session_id" in columns and {"id", "created_at"}.issubset(session_columns)
            join = "LEFT JOIN sessions s ON s.id = n.session_id" if can_join else ""
            session_created = "s.created_at" if can_join else "NULL"
            fields = ("$.metadata.request_id", "$.metadata.generation_model", "$.metadata.started_generation_at",
                "$.metadata.created_at", "$.metadata.metrics.input_tokens", "$.metadata.metrics.output_tokens",
                "$.metadata.metrics.cache_read_tokens", "$.metadata.metrics.cache_creation_tokens")
            projection = ", ".join(
                f"CASE WHEN json_type(n.chat_message, '{field}') IN ('true','false') THEN -1 "
                f"WHEN json_type(n.chat_message, '{field}') IN ('integer','real','text') THEN json_extract(n.chat_message, '{field}') END"
                for field in fields
            )
            rows = connection.execute(f"""SELECT {row_id}, {session_id}, {session_created}, {projection}
                FROM message_nodes n {join}
                WHERE json_valid(n.chat_message) AND json_extract(n.chat_message, '$.role') = 'assistant'
                  AND json_type(n.chat_message, '$.metadata.request_id') = 'text'
                ORDER BY {row_id}""")
            requests = {}
            for row_id, session_id, session_created, request_id, model, started, created, input_value, output_value, cache_read, cache_write in rows:
                request_id = request_id.strip()
                timestamp = _timestamp(started) or _timestamp(created)
                input_value, output_value = valid_token_count(input_value), valid_token_count(output_value)
                cache_read = valid_token_count(0 if cache_read is None else cache_read)
                cache_write = valid_token_count(0 if cache_write is None else cache_write)
                if not request_id or timestamp is None or None in (input_value, output_value, cache_read, cache_write):
                    continue
                session_created = valid_token_count(session_created)
                order = (timestamp, session_created if session_created else float("inf"),
                    session_id if isinstance(session_id, str) else "", -(valid_token_count(row_id) or 0))
                # Match the reference: earliest owning session, newest correction within it.
                previous = requests.get(request_id)
                if previous is None or order < previous[0]:
                    requests[request_id] = (order, input_value + cache_read + cache_write, output_value,
                        model if isinstance(model, str) else None, timestamp)
            input_total = sum(row[1] for row in requests.values())
            output_total = sum(row[2] for row in requests.values())
            if not input_total + output_total:
                return None
            model_rows = [row for row in requests.values() if row[3]]
            model = max(model_rows, key=lambda row: row[4])[3] if model_rows else None
            return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity,
                tokens=input_total + output_total, input_tokens=input_total, output_tokens=output_total,
                model=model, source=str(path))
        except sqlite3.Error:
            return None
        finally:
            if connection is not None:
                connection.close()

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("sessions.db",)):
            snapshot = self._read_database(path)
            if snapshot is not None:
                return snapshot
        return Snapshot.unavailable(self.provider, self.label, "未找到 Devin 已完成 request_id 用量元数据",
            ", ".join(map(str, self.roots)), maturity=self.maturity)
