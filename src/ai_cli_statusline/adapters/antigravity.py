from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .base import Adapter
from .common import newest_files
from .metadata import json_metadata, valid_token_count
from ..models import Snapshot


_SAFE_INTEGER = 2**53 - 1


def _varint(data: memoryview, offset: int) -> tuple[int, int]:
    value = 0
    for index in range(10):
        if offset >= len(data):
            raise ValueError("truncated varint")
        byte = data[offset]
        offset += 1
        if index == 9 and byte > 1:
            raise ValueError("varint exceeds uint64")
        value |= (byte & 127) << (index * 7)
        if not byte & 128:
            return value, offset
    raise ValueError("overlong varint")


def _fields(data: memoryview, allowed: set[int]) -> dict[int, list]:
    """Skip unknown fields without decoding their strings or nested payloads."""
    result = {}
    offset = 0
    while offset < len(data):
        tag, offset = _varint(data, offset)
        field, wire = tag >> 3, tag & 7
        if not 0 < field < 2**29:
            raise ValueError("invalid protobuf tag")
        if wire == 0:
            value, offset = _varint(data, offset)
        elif wire == 2:
            length, offset = _varint(data, offset)
            if length > len(data) - offset:
                raise ValueError("truncated protobuf field")
            value = data[offset:offset + length] if field in allowed else None
            offset += length
        elif wire in (1, 5):
            length = 8 if wire == 1 else 4
            if length > len(data) - offset:
                raise ValueError("truncated fixed field")
            offset += length
            value = None
        else:
            raise ValueError("unsupported protobuf wire type")
        if field in allowed:
            result.setdefault(field, []).append(value)
    return result


def _first(fields: dict, number: int):
    return fields.get(number, [None])[0]


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and 0 <= value <= _SAFE_INTEGER else None


def _generation(raw: object) -> dict | None:
    if not isinstance(raw, bytes):
        return None
    try:
        inner = _first(_fields(memoryview(raw), {1}), 1)
        if not isinstance(inner, memoryview):
            return None
        fields = _fields(inner, {4, 9, 19, 20})
        step = None
        for value in fields.get(20, []):
            if not isinstance(value, memoryview):
                continue
            pair = _fields(value, {1, 2})
            key, value = _first(pair, 1), _first(pair, 2)
            if isinstance(key, memoryview) and key == b"last_step_index" and isinstance(value, memoryview):
                text = bytes(value)
                if text and text.isdigit() and len(text) <= 16:
                    step = _count(int(text))
        if step is None:
            return None
        model = _first(fields, 19)
        model = bytes(model).decode("utf-8").strip() if isinstance(model, memoryview) else None
        context = None
        value = _first(fields, 9)
        if isinstance(value, memoryview):
            value = _first(_fields(value, {10}), 10)
            if isinstance(value, memoryview):
                context = _count(_first(_fields(value, {1}), 1))
        usage = None
        value = _first(fields, 4)
        if isinstance(value, memoryview):
            values = _fields(value, {1, 2, 3, 5, 9, 10})
            counts = {key: _count(_first(values, key)) for key in (1, 2, 3, 5, 9, 10)}
            if any(count is not None for count in counts.values()):
                counts = {key: count or 0 for key, count in counts.items()}
                input_value = counts[1] + counts[2] + counts[5]
                output_value = (counts[9] or max(0, counts[3] - counts[10])) + counts[10]
                usage = (input_value, output_value)
        return {"step": step + 1, "model": model, "context": context, "usage": usage}
    except (ValueError, UnicodeDecodeError):
        return None


class AntigravityAdapter(Adapter):
    """Only completed planner usage from explicit generation metadata."""

    provider, label, maturity = "antigravity", "Antigravity", "experimental"

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.roots = roots if roots is not None else [Path.home() / ".gemini" / name / "conversations"
            for name in ("antigravity", "antigravity-ide", "antigravity-cli")]

    def _transcript(self, path: Path) -> Path:
        return path.parent.parent / "brain" / path.stem / ".system_generated" / "logs" / "transcript.jsonl"

    def _read_database(self, path: Path) -> Snapshot | None:
        connection = None
        try:
            completed = set()
            for row in json_metadata(self._transcript(path), {
                "type": "$.type", "step": "$.step_index", "created": "$.created_at",
            }):
                step = valid_token_count(row["step"])
                if row["type"] == "PLANNER_RESPONSE" and step is not None and isinstance(row["created"], str):
                    try:
                        datetime.fromisoformat(row["created"].replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    completed.add(step)
            connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=1)
            connection.execute("PRAGMA query_only=ON")
            observations = {}
            # gen_metadata is a dedicated metadata blob; no messages/auth table is opened.
            for _index, raw in connection.execute("SELECT idx, data FROM gen_metadata ORDER BY idx"):
                info = _generation(raw)
                if info is not None and info["step"] in completed:
                    observations[info["step"]] = info
            usage = [row["usage"] for row in observations.values() if row["usage"] is not None]
            input_total = sum(row[0] for row in usage)
            output_total = sum(row[1] for row in usage)
            if not input_total + output_total:
                return None
            latest = max(observations.values(), key=lambda row: row["step"])
            return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity,
                tokens=input_total + output_total, input_tokens=input_total, output_tokens=output_total,
                model=latest["model"], context_used=latest["context"], source=str(path))
        except (sqlite3.Error, OSError):
            return None
        finally:
            if connection is not None:
                connection.close()

    def snapshot(self) -> Snapshot:
        def modified(path):
            candidates = (path, path.with_name(path.name + "-wal"), self._transcript(path))
            return max((item.stat().st_mtime for item in candidates if item.exists()), default=0)
        paths = newest_files(self.roots, ("*.db",))
        try:
            paths.sort(key=modified, reverse=True)
        except OSError:
            pass
        for path in paths:
            if path.parent.name != "conversations":
                continue
            snapshot = self._read_database(path)
            if snapshot is not None:
                return snapshot
        return Snapshot.unavailable(self.provider, self.label, "未找到 Antigravity 已完成 planner token 元数据；不采用字符估算",
            ", ".join(map(str, self.roots)), maturity=self.maturity)
