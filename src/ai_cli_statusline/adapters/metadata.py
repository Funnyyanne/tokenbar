from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Iterator

from ..models import as_int


def valid_token_count(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    number = as_int(value)
    if number is None or number < 0 or isinstance(value, float) and value != number:
        return None
    return number


def token_count(value: object) -> int:
    return valid_token_count(value) or 0


def json_records_metadata(records: Iterable[bytes], fields: dict[str, str], *,
    types: dict[str, str] | None = None, stop_on_invalid: bool = False) -> Iterator[dict]:
    """Return only scalar paths/types from plaintext or decompressed records."""
    types = types or {}
    connection = sqlite3.connect(":memory:")
    columns = ["CASE WHEN json_type(value, ?) IN ('true','false') THEN -1 WHEN json_type(value, ?) IN ('integer', 'real', 'text') THEN json_extract(value, ?) END" for _ in fields]
    columns.extend("json_type(value, ?)" for _ in types)
    projection = ", ".join(columns)
    parameters = (*tuple(item for path_value in fields.values() for item in (path_value, path_value, path_value)), *types.values())
    query = f"WITH payload(value) AS (VALUES (?)) SELECT {projection} FROM payload WHERE json_valid(value) AND json_type(value) = 'object'"
    try:
        for raw in records:
            if not raw.strip():
                continue
            try:
                row = connection.execute(query, (raw.decode("utf-8"), *parameters)).fetchone()
            except (UnicodeDecodeError, sqlite3.Error):
                row = None
            if row is None:
                if stop_on_invalid:
                    break
                continue
            yield dict(zip((*fields, *types), row))
    finally:
        connection.close()


def json_metadata(path: Path, fields: dict[str, str], *, lines: bool = True,
    types: dict[str, str] | None = None) -> Iterator[dict]:
    """Stream fixed metadata paths; full prompt/response objects stay undecoded."""
    with path.open("rb") as handle:
        yield from json_records_metadata(handle if lines else (handle.read(),), fields, types=types)


def json_array_metadata(path: Path, fields: dict[str, str]) -> Iterator[dict]:
    """Read Cline's array or messages envelope, returning scalar metadata only."""
    connection = sqlite3.connect(":memory:")
    projection = ", ".join("CASE WHEN json_type(item.value, ?) IN ('integer', 'real', 'text') THEN json_extract(item.value, ?) END" for _ in fields)
    parameters = tuple(item for path_value in fields.values() for item in (path_value, path_value))
    query = f"""WITH payload(value) AS (VALUES (?)), valid(value) AS (
        SELECT CASE WHEN json_valid(value) THEN value ELSE '[]' END FROM payload
    ) SELECT {projection} FROM valid, json_each(valid.value,
        CASE WHEN json_type(valid.value) = 'array' THEN '$' ELSE '$.messages' END) AS item
        WHERE item.type = 'object'"""
    try:
        try:
            rows = connection.execute(query, (path.read_text(encoding="utf-8"), *parameters))
            for row in rows:
                yield dict(zip(fields, row))
        except (UnicodeDecodeError, sqlite3.Error):
            return
    finally:
        connection.close()
