from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .base import Adapter
from .common import newest_files
from ..models import Snapshot, as_int


@dataclass(frozen=True, slots=True)
class SqliteSchema:
    """Positive allowlist for one provider-owned usage table."""

    table: str
    input_columns: tuple[str, ...] = ()
    output_columns: tuple[str, ...] = ()
    cache_columns: tuple[str, ...] = ()
    total_columns: tuple[str, ...] = ()
    model_column: str | None = None


def _quote(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


class SqliteAdapter(Adapter):
    """Read only explicitly allowlisted usage columns from SQLite databases."""

    def __init__(
        self,
        provider: str,
        roots: list[Path],
        *,
        schemas: tuple[SqliteSchema, ...] = (),
        patterns: tuple[str, ...] = ("*.sqlite", "*.sqlite3", "*.db"),
        maturity: str = "experimental",
    ) -> None:
        self.provider = provider
        self.label = provider.replace("-", " ").replace("_", " ").title()
        self.roots = roots
        self.schemas = schemas
        self.patterns = patterns
        self.maturity = maturity

    def _read_schema(self, connection: sqlite3.Connection, schema: SqliteSchema) -> tuple[int, int | None, int | None, str | None] | None:
        columns = connection.execute(f"PRAGMA table_info({_quote(schema.table)})").fetchall()
        available = {row[1] for row in columns if isinstance(row[1], str)}
        inputs = tuple(name for name in schema.input_columns if name in available)
        outputs = tuple(name for name in schema.output_columns if name in available)
        caches = tuple(name for name in schema.cache_columns if name in available)
        totals = tuple(name for name in schema.total_columns if name in available)
        model_column = schema.model_column if schema.model_column in available else None
        usage_columns = inputs + outputs + caches
        if not usage_columns:
            usage_columns = totals
        if not usage_columns:
            return None

        selected = usage_columns + ((model_column,) if model_column else ())
        query = f"SELECT {', '.join(_quote(name) for name in selected)} FROM {_quote(schema.table)}"
        input_total = output_total = cache_total = overall_total = 0
        model: str | None = None
        for row in connection.execute(query):
            values = dict(zip(selected, row))
            if inputs or outputs or caches:
                input_total += sum(as_int(values.get(name)) or 0 for name in inputs)
                output_total += sum(as_int(values.get(name)) or 0 for name in outputs)
                cache_total += sum(as_int(values.get(name)) or 0 for name in caches)
            else:
                overall_total += sum(as_int(values.get(name)) or 0 for name in totals)
            candidate_model = values.get(model_column) if model_column else None
            if isinstance(candidate_model, str) and candidate_model:
                model = candidate_model

        if inputs or outputs or caches:
            score = input_total + output_total + cache_total
            input_tokens: int | None = input_total + cache_total
            output_tokens: int | None = output_total
        else:
            score = overall_total
            input_tokens = None
            output_tokens = None
        if score <= 0:
            return None
        return score, input_tokens, output_tokens, model

    def _read_database(self, path: Path) -> Snapshot | None:
        if not self.schemas:
            return None
        try:
            connection = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
        except sqlite3.Error:
            return None
        try:
            tables = {
                table
                for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                if isinstance(table, str)
            }
            best: tuple[int, int | None, int | None, str | None] | None = None
            for schema in self.schemas:
                if schema.table not in tables:
                    continue
                result = self._read_schema(connection, schema)
                if result is not None and (best is None or result[0] > best[0]):
                    best = result
            if best is None:
                return None
            return Snapshot(
                provider=self.provider,
                label=self.label,
                maturity=self.maturity,
                model=best[3],
                tokens=best[0],
                input_tokens=best[1],
                output_tokens=best[2],
                source=str(path),
            )
        except sqlite3.Error:
            return None
        finally:
            connection.close()

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, self.patterns):
            snapshot = self._read_database(path)
            if snapshot is not None:
                return snapshot
        return Snapshot.unavailable(
            self.provider,
            self.label,
            "未找到可识别 token 字段",
            ", ".join(map(str, self.roots)),
            maturity=self.maturity,
        )
