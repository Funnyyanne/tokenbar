from __future__ import annotations

import sqlite3
from pathlib import Path

from .base import Adapter
from .common import newest_files
from ..models import Snapshot, as_int


class SqliteAdapter(Adapter):
    """Best-effort read-only token counter for SQLite-backed CLI tools."""

    TOKEN_COLUMNS = ("input", "output", "prompt", "completion", "cache", "token")

    def __init__(self, provider: str, roots: list[Path]) -> None:
        self.provider = provider
        self.label = provider.replace("-", " ").replace("_", " ").title()
        self.roots = roots

    def _read_database(self, path: Path) -> Snapshot | None:
        try:
            connection = sqlite3.connect(f"file:{path.absolute()}?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
        except sqlite3.Error:
            return None
        try:
            best: tuple[int, int, int, str | None] | None = None
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for (table,) in tables:
                if not isinstance(table, str) or table.startswith("sqlite_"):
                    continue
                columns = connection.execute(f'PRAGMA table_info("{table.replace(chr(34), chr(34) * 2)}")').fetchall()
                names = [row[1] for row in columns if isinstance(row[1], str)]
                token_names = [name for name in names if any(part in name.lower() for part in self.TOKEN_COLUMNS)]
                if not token_names:
                    continue
                quoted = ", ".join(f'"{name.replace(chr(34), chr(34) * 2)}"' for name in token_names)
                model_name = next((name for name in names if name.lower() in {"model", "model_name", "modelname"}), None)
                model_sql = f', "{model_name.replace(chr(34), chr(34) * 2)}"' if model_name else ""
                rows = connection.execute(f'SELECT {quoted}{model_sql} FROM "{table.replace(chr(34), chr(34) * 2)}" LIMIT 10000').fetchall()
                inputs = outputs = cache = total = 0
                model: str | None = None
                for row in rows:
                    for name, value in zip(token_names, row):
                        amount = as_int(value) or 0
                        lowered = name.lower()
                        if "cache" in lowered:
                            cache += amount
                        elif "input" in lowered or "prompt" in lowered:
                            inputs += amount
                        elif "output" in lowered or "completion" in lowered:
                            outputs += amount
                        else:
                            total += amount
                    if model_name and isinstance(row[-1], str):
                        model = row[-1]
                score = inputs + outputs + cache + total
                if score and (best is None or score > best[0]):
                    best = (score, inputs + cache, outputs + total, model)
            if best is None:
                return None
            return Snapshot(self.provider, self.label, model=best[3], tokens=best[0], input_tokens=best[1], output_tokens=best[2], source=str(path))
        except sqlite3.Error:
            return None
        finally:
            connection.close()

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, ("*.sqlite", "*.sqlite3", "*.db")):
            snapshot = self._read_database(path)
            if snapshot is not None:
                return snapshot
        return Snapshot.unavailable(self.provider, self.label, "未找到可识别 token 字段", ", ".join(map(str, self.roots)))
