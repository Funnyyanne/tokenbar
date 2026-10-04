from __future__ import annotations

import os
import re
from pathlib import Path

from .common import newest_files
from .metadata import json_records_metadata, valid_token_count
from .terminal import SessionMetadataAdapter
from ..models import Snapshot


_FINAL_RESPONSE = re.compile(rb'(?:^|\n)(?:\[[^\r\n]*\][ \t]*)?Final response:[ \t\r\n]*\{')
_MAX_RESPONSE = 128 * 1024 * 1024


def _responses(path: Path):
    """Frame completed JSON responses without decoding any message content."""
    buffer = bytearray()
    active = False
    index = depth = 0
    in_string = escaped = False
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            buffer.extend(chunk)
            while True:
                if not active:
                    marker = _FINAL_RESPONSE.search(buffer)
                    if marker is None:
                        # Only an incomplete marker needs to cross read boundaries.
                        buffer = buffer[-512:]
                        break
                    buffer = buffer[marker.end() - 1:]
                    active, index, depth, in_string, escaped = True, 0, 0, False, False
                end = None
                while index < len(buffer):
                    byte = buffer[index]
                    index += 1
                    if in_string:
                        if escaped:
                            escaped = False
                        elif byte == 92:
                            escaped = True
                        elif byte == 34:
                            in_string = False
                    elif byte == 34:
                        in_string = True
                    elif byte == 123:
                        depth += 1
                    elif byte == 125:
                        depth -= 1
                        if depth == 0:
                            end = index
                            break
                if end is not None:
                    if end > _MAX_RESPONSE:
                        raise OSError("最终响应日志超过 128 MiB")
                    yield bytes(buffer[:end])
                    buffer = buffer[end:]
                    active = False
                else:
                    if len(buffer) > _MAX_RESPONSE:
                        raise OSError("最终响应日志超过 128 MiB")
                    break


class LMStudioAdapter(SessionMetadataAdapter):
    """Reported final-response usage for lms/development-server logs."""

    provider, label = "lmstudio", "LM Studio"
    patterns = ("*.log", "*.LOG")
    fields = {"id": "$.id", "model": "$.model"}
    for _name in ("prompt_tokens", "promptTokens", "input_tokens", "inputTokens",
        "completion_tokens", "completionTokens", "output_tokens", "outputTokens", "total_tokens", "totalTokens"):
        fields[_name] = "$.usage." + _name
    del _name

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("LM_STUDIO_HOME", Path.home() / ".lmstudio")).expanduser()
        super().__init__(roots if roots is not None else [home / "server-logs"])

    def records(self, path: Path):
        for row in json_records_metadata(_responses(path), self.fields):
            # The response ID owns usage; arbitrary request/user IDs are ignored.
            identity = row["id"]
            if not isinstance(identity, str) or not identity.startswith(("chatcmpl-", "cmpl-", "resp_")):
                row["id"] = None
            yield row

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        def pick(*keys):
            return valid_token_count(next((row[key] for key in keys if row[key] is not None), 0))

        input_value = pick("prompt_tokens", "promptTokens", "input_tokens", "inputTokens")
        output_value = pick("completion_tokens", "completionTokens", "output_tokens", "outputTokens")
        total = pick("total_tokens", "totalTokens")
        if None in (input_value, output_value, total):
            return None
        # Cache/reasoning details are subsets of the parents. Reported total
        # can include an extra input portion, as in the upstream normalization.
        total = max(total, input_value + output_value)
        return (total - output_value, output_value, total) if total else None

    def snapshot(self) -> Snapshot:
        observations = {}
        model = None
        # Server logs rotate rather than representing individual sessions.
        # Visit oldest first so newer response corrections replace mirrors.
        for path in reversed(list(newest_files(self.roots, self.patterns))):
            local = {}
            latest_model = None
            try:
                for index, row in enumerate(self.records(path)):
                    usage = self.usage(row)
                    if usage is None:
                        continue
                    identity = row["id"] or (path, index)
                    local[identity] = usage
                    if isinstance(row["model"], str) and row["model"]:
                        latest_model = row["model"]
            except OSError:
                continue
            observations.update(local)
            model = latest_model or model
        total = sum(row[2] for row in observations.values())
        source = ", ".join(map(str, self.roots))
        if total:
            return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity,
                tokens=total, input_tokens=sum(row[0] for row in observations.values()),
                output_tokens=sum(row[1] for row in observations.values()), model=model, source=source)
        return Snapshot.unavailable(self.provider, self.label, "未找到 LM Studio 最终响应用量元数据", source, maturity=self.maturity)
