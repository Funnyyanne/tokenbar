from __future__ import annotations

import sqlite3
from pathlib import Path

from .sqlite import SqliteAdapter, SqliteSchema
from ..models import Snapshot, as_int


class OpenCodeAdapter(SqliteAdapter):
    """Read materialized usage or legacy JSON usage via SQLite extraction."""

    provider = "opencode"
    label = "OpenCode"

    def __init__(self, roots: list[Path] | None = None) -> None:
        roots = roots or [
            Path.home() / ".local" / "share" / "opencode",
            Path.home() / ".opencode",
        ]
        super().__init__(
            self.provider,
            roots,
            schemas=(
                SqliteSchema(
                    table="session",
                    input_columns=("tokens_input",),
                    output_columns=("tokens_output", "tokens_reasoning"),
                    cache_columns=("tokens_cache_read", "tokens_cache_write"),
                ),
            ),
            patterns=("opencode.db", "db.sqlite", "*.db", "*.sqlite"),
            maturity="stable",
        )
        self.label = "OpenCode"

    def _legacy_filter(self) -> str:
        return ""

    def _read_database(self, path: Path) -> Snapshot | None:
        materialized = super()._read_database(path)
        if materialized is not None:
            return materialized
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
            columns = {
                row[1]
                for row in connection.execute('PRAGMA table_info("message")')
                if isinstance(row[1], str)
            }
            if "data" not in columns:
                return None
            row = connection.execute(
                f'''SELECT
                    SUM(COALESCE(json_extract(data, '$.tokens.input'), 0)),
                    SUM(COALESCE(json_extract(data, '$.tokens.output'), 0)),
                    SUM(COALESCE(json_extract(data, '$.tokens.reasoning'), 0)),
                    SUM(COALESCE(json_extract(data, '$.tokens.cache.read'), 0)),
                    SUM(COALESCE(json_extract(data, '$.tokens.cache.write'), 0)),
                    MAX(COALESCE(json_extract(data, '$.modelID'), json_extract(data, '$.model.modelID'),
                        CASE WHEN json_type(data, '$.model') = 'text' THEN json_extract(data, '$.model') END))
                FROM message
                WHERE json_valid(data) AND json_extract(data, '$.role') = 'assistant'
                {self._legacy_filter()} '''
            ).fetchone()
        except sqlite3.Error:
            return None
        finally:
            if connection is not None:
                connection.close()
        input_value, output_value, reasoning, cache_read, cache_write, model = row
        input_tokens = as_int(input_value) or 0
        output_tokens = (as_int(output_value) or 0) + (as_int(reasoning) or 0)
        cache_tokens = (as_int(cache_read) or 0) + (as_int(cache_write) or 0)
        total = input_tokens + output_tokens + cache_tokens
        if total <= 0:
            return None
        return Snapshot(
            provider=self.provider,
            label=self.label,
            maturity=self.maturity,
            model=model if isinstance(model, str) else None,
            tokens=total,
            input_tokens=input_tokens + cache_tokens,
            output_tokens=output_tokens,
            source=str(path),
        )
