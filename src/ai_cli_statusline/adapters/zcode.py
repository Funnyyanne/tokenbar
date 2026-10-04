from __future__ import annotations

import sqlite3
from pathlib import Path

from .base import Adapter
from .common import newest_files
from .metadata import valid_token_count
from ..models import Snapshot


def _native_provider(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    return not any(vendor in value.lower() for vendor in ("anthropic", "openai", "google"))


class ZCodeAdapter(Adapter):
    """Native ledger plus pre-ledger history; exclude bundled CLI mirrors."""

    provider, label, maturity = "zcode", "ZCode", "experimental"

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.roots = roots if roots is not None else [Path.home() / ".zcode" / "cli" / "db"]

    def _read_database(self, path: Path) -> Snapshot | None:
        connection = None
        try:
            connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
            columns = {row[1] for row in connection.execute('PRAGMA table_info("model_usage")')}
            required = {"id", "logical_request_id", "attempt_index", "session_id", "provider_id", "model_id",
                "status", "started_at", "input_tokens", "output_tokens"}
            native = {}
            if required.issubset(columns):
                optional = ("cache_creation_input_tokens", "cache_read_input_tokens", "reasoning_tokens",
                    "provider_total_tokens", "computed_total_tokens")
                projection = ", ".join(name if name in columns else "NULL" for name in optional)
                for identity, request_id, attempt, session_id, provider, model, started, raw_input, raw_output, cache_write, cache_read, reasoning, provider_total, computed_total in connection.execute(f"""
                    SELECT id, logical_request_id, attempt_index, session_id, provider_id, model_id,
                        started_at, input_tokens, output_tokens, {projection} FROM model_usage
                    WHERE status = 'completed' ORDER BY started_at, id"""
                ):
                    input_value, output_value = valid_token_count(raw_input), valid_token_count(raw_output)
                    started = valid_token_count(started)
                    if not (_native_provider(provider) and isinstance(model, str) and model.strip()
                        and isinstance(session_id, str) and session_id.strip() and started):
                        continue
                    if (raw_input is not None and input_value is None
                        or raw_output is not None and output_value is None):
                        continue
                    # Parents include these subsets; only absent/zero parents fall back.
                    input_value = input_value or (valid_token_count(cache_write) or 0) + (valid_token_count(cache_read) or 0)
                    output_value = output_value or valid_token_count(reasoning) or 0
                    total = valid_token_count(provider_total) or valid_token_count(computed_total) or input_value + output_value
                    if not total:
                        continue
                    identity = identity or (f"{request_id}#{attempt}" if request_id else None)
                    if not isinstance(identity, str) or not identity.strip():
                        continue
                    native[identity] = (input_value, output_value, model, started, total)
            boundary = min((row[3] for row in native.values()), default=None)
            legacy = {}
            columns = {row[1] for row in connection.execute('PRAGMA table_info("message")')}
            if "data" in columns:
                identity = "id" if "id" in columns else "rowid"
                updated = "time_updated" if "time_updated" in columns else "json_extract(data, '$.time.created')"
                for key, timestamp, provider, model, input_value, output_value in connection.execute(f"""
                    SELECT {identity}, {updated},
                        COALESCE(CASE WHEN json_type(data, '$.providerID') = 'text' THEN json_extract(data, '$.providerID') END,
                            CASE WHEN json_type(data, '$.model.providerID') = 'text' THEN json_extract(data, '$.model.providerID') END),
                        COALESCE(CASE WHEN json_type(data, '$.modelID') = 'text' THEN json_extract(data, '$.modelID') END,
                            CASE WHEN json_type(data, '$.model.modelID') = 'text' THEN json_extract(data, '$.model.modelID') END),
                        CASE WHEN json_type(data, '$.tokens.input') IN ('integer','real') THEN json_extract(data, '$.tokens.input') END,
                        CASE WHEN json_type(data, '$.tokens.output') IN ('integer','real') THEN json_extract(data, '$.tokens.output') END
                    FROM message WHERE json_valid(data) AND json_extract(data, '$.role') = 'assistant'
                    ORDER BY {updated}, {identity}"""
                ):
                    input_value, output_value = valid_token_count(input_value), valid_token_count(output_value)
                    timestamp = valid_token_count(timestamp)
                    if not _native_provider(provider) or input_value is None or output_value is None:
                        continue
                    if boundary is not None and (not timestamp or timestamp >= boundary):
                        continue
                    legacy[key] = (input_value, output_value, model if isinstance(model, str) else None,
                        timestamp or 0, input_value + output_value)
            observations = [*legacy.values(), *native.values()]
            input_total = sum(row[0] for row in observations)
            output_total = sum(row[1] for row in observations)
            total = sum(row[4] for row in observations)
            if not total:
                return None
            models = [row for row in observations if row[2]]
            return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity,
                tokens=total, input_tokens=input_total, output_tokens=output_total,
                model=max(models, key=lambda row: row[3])[2] if models else None, source=str(path))
        except sqlite3.Error:
            return None
        finally:
            if connection is not None:
                connection.close()

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("db.sqlite",)):
            snapshot = self._read_database(path)
            if snapshot is not None:
                return snapshot
        return Snapshot.unavailable(self.provider, self.label, "未找到 ZCode 原生非镜像用量元数据",
            ", ".join(map(str, self.roots)), maturity=self.maturity)
