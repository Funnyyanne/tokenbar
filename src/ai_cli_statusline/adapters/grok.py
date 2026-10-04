from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .metadata import json_metadata, valid_token_count
from .terminal import SessionMetadataAdapter


_USAGE_FIELDS = (
    "inputTokens", "input_tokens", "outputTokens", "output_tokens", "totalTokens", "total_tokens",
    "cachedReadTokens", "cacheReadInputTokens", "cache_read_input_tokens", "cached_input_tokens",
    "cacheCreationTokens", "cachedWriteTokens", "cacheWriteInputTokens", "cache_creation_input_tokens",
)


def _projection(value: str, paths: list[str]) -> str:
    return ", ".join(
        f"CASE WHEN json_type({value}, '{path}') IN ('integer','real','text') THEN json_extract({value}, '{path}') "
        f"WHEN json_type({value}, '{path}') IS NOT NULL AND json_type({value}, '{path}') != 'null' THEN -1 END"
        for path in paths
    )


def _usage(row: dict) -> tuple[int, int, int] | None:
    if all(row[key] is None for key in _USAGE_FIELDS):
        return None

    def pick(*keys):
        value = next((row[key] for key in keys if row[key] is not None), 0)
        return valid_token_count(value)

    input_value = pick("inputTokens", "input_tokens")
    output_value = pick("outputTokens", "output_tokens")
    cache_read = pick("cachedReadTokens", "cacheReadInputTokens", "cache_read_input_tokens", "cached_input_tokens")
    cache_write = pick("cacheCreationTokens", "cachedWriteTokens", "cacheWriteInputTokens", "cache_creation_input_tokens")
    total = pick("totalTokens", "total_tokens")
    if None in (input_value, output_value, cache_read, cache_write, total):
        return None
    # CamelCase parents include cache; headless snake_case input is disjoint.
    input_value = max(input_value, cache_read + cache_write) if row["inputTokens"] is not None else input_value + cache_read + cache_write
    total = total or input_value + output_value
    return input_value, output_value, total


class GrokAdapter(SessionMetadataAdapter):
    """Only reported turn usage; context watermarks are never billed tokens."""

    provider, label = "grok", "Grok Build"
    patterns = ("updates.jsonl",)

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("GROK_HOME", Path.home() / ".grok")).expanduser()
        super().__init__(roots if roots is not None else [home / "sessions"])

    def records(self, path: Path):
        fallback_model = None
        try:
            for row in json_metadata(path.with_name("signals.json"), {
                "primary": "$.primaryModelId", "first": "$.modelsUsed[0]", "model": "$.model",
            }, lines=False):
                fallback_model = row["primary"] or row["first"] or row["model"]
        except OSError:
            pass
        fields = ["id", "root_id", "event_id", "record_id", "prompt_id", *_USAGE_FIELDS]
        paths = ["$.params._meta.eventId", "$._meta.eventId", "$.eventId", "$.id", "$.params.update.prompt_id",
            *("$.params.update.usage." + key for key in _USAGE_FIELDS)]
        query = f"""WITH record(value) AS (VALUES (?)) SELECT {_projection('value', paths)} FROM record
            WHERE json_valid(value) AND json_extract(value, '$.params.update.sessionUpdate') = 'turn_completed'
              AND json_type(value, '$.params.update.usage') = 'object'"""
        model_value = "CASE WHEN item.type = 'object' THEN item.value ELSE '{}' END"
        model_query = f"""SELECT item.key, item.type, {_projection(model_value, ['$.' + key for key in _USAGE_FIELDS])}
            FROM (SELECT ? AS value) record, json_each(record.value, '$.params.update.usage.modelUsage') item
            WHERE json_type(record.value, '$.params.update.usage.modelUsage') = 'object'"""
        connection = sqlite3.connect(":memory:")
        try:
            with path.open("rb") as handle:
                for raw in handle:
                    try:
                        text = raw.decode("utf-8")
                        values = connection.execute(query, (text,)).fetchone()
                        if values is None:
                            continue
                        row = dict(zip(fields, values))
                        identity = next((row[key] for key in fields[:5] if row[key] is not None), None)
                        # Replace a whole turn on correction, including its previous model map.
                        row["id"] = str(identity) if isinstance(identity, (str, int)) else None
                        models = []
                        complete = True
                        for model, kind, *values in connection.execute(model_query, (text,)):
                            usage = _usage(dict(zip(_USAGE_FIELDS, values))) if kind == "object" else None
                            if usage is None:
                                complete = False
                            else:
                                models.append((*usage, model if isinstance(model, str) else None))
                        if complete and any(value[2] > 0 for value in models):
                            row["usage"] = tuple(sum(value[index] for value in models) for index in range(3))
                            row["model"] = models[-1][3]
                        else:
                            row["usage"] = _usage(row)
                            row["model"] = fallback_model
                        yield row
                    except (UnicodeDecodeError, sqlite3.Error):
                        continue
        finally:
            connection.close()

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        return row["usage"]
