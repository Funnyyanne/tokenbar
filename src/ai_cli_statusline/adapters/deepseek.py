from __future__ import annotations

import os
import re
from pathlib import Path

from .metadata import json_records_metadata, valid_token_count
from .terminal import SessionMetadataAdapter


_LOG_NAME = re.compile(r"session(?:\.v(\d+))?\.jsonl(?:\.zstd)?$")
_MAX_COMPRESSED = 64 * 1024 * 1024
_MAX_TEXT = 128 * 1024 * 1024
_USAGE_FIELDS = ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens", "reasoningTokens")


def _decompressed_records(path: Path):
    # Validate every frame before exposing any usage from this artifact. In
    # particular, a truncated frame must not look like a completed session.
    try:
        import zstandard
    except ImportError as error:
        raise OSError("读取压缩日志需要项目依赖 zstandard") from error
    output = bytearray()
    decoder = None
    compressed_size = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024):
                compressed_size += len(chunk)
                if compressed_size > _MAX_COMPRESSED:
                    raise OSError("压缩日志超过 64 MiB")
                while chunk:
                    if decoder is None:
                        decoder = zstandard.ZstdDecompressor(max_window_size=64 * 1024).decompressobj()
                    output.extend(decoder.decompress(chunk))
                    if len(output) > _MAX_TEXT:
                        raise OSError("解压日志超过 128 MiB")
                    chunk = decoder.unused_data if decoder.eof else b""
                    if decoder.eof:
                        decoder = None
        if decoder is not None:
            raise OSError("压缩日志末帧未完成")
    except zstandard.ZstdError as error:
        raise OSError("压缩日志格式无效") from error
    yield from output.splitlines()


class DeepSeekAdapter(SessionMetadataAdapter):
    """DeepSeek Harness v0/v3 explicit usage, including concatenated zstd."""

    provider, label = "deepseek", "DeepSeek"
    patterns = ("session*.jsonl", "session*.jsonl.zstd")

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("DSH_HOME", Path.home() / ".dsh")).expanduser()
        super().__init__(roots if roots is not None else [home / "sessions"])

    def accepts_path(self, path: Path) -> bool:
        if not _LOG_NAME.fullmatch(path.name):
            return False
        try:
            candidates = [item for item in path.parent.iterdir() if item.is_file() and _LOG_NAME.fullmatch(item.name)]
            selected = max(candidates, key=lambda item: (item.stat().st_mtime_ns,
                int(_LOG_NAME.fullmatch(item.name).group(1) or 0), item.name.endswith(".zstd")))
            return selected == path
        except (OSError, ValueError):
            return False

    def records(self, path: Path):
        fields = {"type": "$.type", "seq": "$.seq", "time": "$.time", "timestamp": "$.timestamp",
            "data_time": "$.data.time", "data_timestamp": "$.data.timestamp", "message_id": "$.data.message.id",
            "model": "$.data.message.source.model", "data_model": "$.data.model",
            "header_model": "$.data.header.config.model"}
        for key in _USAGE_FIELDS:
            fields[key] = "$.data.usage." + key
            fields["root_" + key] = "$.usage." + key
        header_model = None
        with path.open("rb") as handle:
            records = _decompressed_records(path) if path.name.endswith(".zstd") else handle
            for row in json_records_metadata(records, fields,
                types={"usage_type": "$.data.usage", "data_type": "$.data"}, stop_on_invalid=True):
                if row["type"] == "request/header":
                    header_model = row["header_model"] or header_model
                    continue
                if row["type"] not in {"assistant/message", "message/assistant"}:
                    continue
                if row["data_type"] != "object":
                    continue
                model = row["model"] or row["data_model"] or header_model
                if not isinstance(model, str) or not model.strip():
                    continue
                if not any(valid_token_count(row[key]) for key in ("time", "timestamp", "data_time", "data_timestamp")):
                    continue
                row["model"] = model.strip().rsplit("/", 1)[-1]
                seq = valid_token_count(row["seq"])
                row["id"] = "seq:" + str(seq) if seq is not None else row["message_id"]
                if row["usage_type"] is None:
                    for key in _USAGE_FIELDS:
                        row[key] = row["root_" + key]
                elif row["usage_type"] != "object":
                    continue
                yield row

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        values = [valid_token_count(0 if row[key] is None else row[key]) for key in _USAGE_FIELDS]
        if None in values:
            return None
        input_value = values[0] + values[2] + values[3]
        output_value = values[1] + values[4]
        total = input_value + output_value
        return (input_value, output_value, total) if total else None
