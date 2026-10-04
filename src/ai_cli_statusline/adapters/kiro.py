from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .metadata import valid_token_count
from .terminal import SessionMetadataAdapter


_SESSION_NAME = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.json$", re.I)


class KiroAdapter(SessionMetadataAdapter):
    """Only explicit legacy CLI counters; never estimate chars or credits."""

    provider, label = "kiro", "Kiro"
    patterns = ("*.json",)

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("KIRO_HOME", Path.home() / ".kiro")).expanduser()
        super().__init__(roots if roots is not None else [home / "sessions"])

    def accepts_path(self, path: Path) -> bool:
        return path.parent.name == "cli" and bool(_SESSION_NAME.fullmatch(path.name))

    def records(self, path: Path):
        fields = {
            "session": ("record.value", "$.session_id"),
            "session_model": ("record.value", "$.session_state.rts_model_state.model_info.model_id"),
            "session_model_name": ("record.value", "$.session_state.rts_model_state.model_info.model_name"),
            "rand": ("turn.value", "$.loop_id.rand"), "seed": ("turn.value", "$.loop_id.seed"),
            "message": ("turn.value", "$.message_ids[0]"), "model": ("turn.value", "$.model_id"),
            "input": ("turn.value", "$.input_token_count"), "output": ("turn.value", "$.output_token_count"),
            "started_ms": ("turn.value", "$.request_start_timestamp_ms"),
            "started": ("turn.value", "$.start_timestamp"), "ended": ("turn.value", "$.end_timestamp"),
        }
        projection = ", ".join(f"CASE WHEN json_type({value}, '{key}') IN ('true','false') THEN -1 "
            f"WHEN json_type({value}, '{key}') IN ('integer','real','text') THEN json_extract({value}, '{key}') END"
            for value, key in fields.values())
        array = "$.session_state.conversation_metadata.user_turn_metadatas"
        query = f"""WITH payload(value) AS (VALUES (?)), record(value) AS (
            SELECT value FROM payload WHERE json_valid(value)
        ) SELECT {projection} FROM record, json_each(record.value, '{array}') turn
            WHERE json_type(record.value, '{array}') = 'array' AND turn.type = 'object'"""
        connection = sqlite3.connect(":memory:")
        try:
            try:
                rows = connection.execute(query, (path.read_text(encoding="utf-8"),))
                for values in rows:
                    row = dict(zip(fields, values))
                    timestamp = valid_token_count(row["started_ms"])
                    if not timestamp:
                        value = row["started"] or row["ended"]
                        if not isinstance(value, str):
                            continue
                        try:
                            datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                    session = row["session"] if isinstance(row["session"], str) and row["session"] else path.stem
                    loop = row["rand"] if row["rand"] is not None else row["seed"]
                    if isinstance(loop, (str, int)) and loop != -1:
                        row["id"] = f"{session}:{loop}"
                    elif isinstance(row["message"], str) and row["message"]:
                        row["id"] = row["message"]
                    else:
                        continue
                    row["model"] = row["model"] or row["session_model"] or row["session_model_name"]
                    yield row
            except (UnicodeDecodeError, sqlite3.Error):
                return
        finally:
            connection.close()

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        input_value = valid_token_count(row["input"])
        output_value = valid_token_count(row["output"])
        if input_value is None or output_value is None:
            return None
        total = input_value + output_value
        return (input_value, output_value, total) if total else None
