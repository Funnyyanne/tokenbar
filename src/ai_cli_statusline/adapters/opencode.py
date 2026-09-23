from __future__ import annotations

from pathlib import Path

from .sqlite import SqliteAdapter, SqliteSchema


class OpenCodeAdapter(SqliteAdapter):
    """Read OpenCode's materialized session usage without reading messages."""

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
