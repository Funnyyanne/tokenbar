from __future__ import annotations

import heapq
from pathlib import Path
from typing import Any, Iterator

from ..models import as_int


def iter_json_objects(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for key, child in value.items():
            if key in {"usage", "token_usage", "tokenUsage", "usage_metadata", "usageMetadata"}:
                continue
            yield from iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_objects(child)


def usage_from_object(obj: dict[str, Any]) -> dict[str, int] | None:
    candidates: list[dict[str, Any]] = []
    for key in ("usage", "token_usage", "tokenUsage", "usage_metadata", "usageMetadata"):
        value = obj.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    if any(key in obj for key in (
        "input_tokens", "output_tokens", "inputTokens", "outputTokens",
        "prompt_tokens", "completion_tokens", "promptTokens", "completionTokens",
        "inputOther", "output", "inputCacheRead", "inputCacheCreation",
    )):
        candidates.append(obj)
    for candidate in candidates:
        input_value = as_int(candidate.get("input_tokens", candidate.get("inputTokens", candidate.get("prompt_tokens", candidate.get("promptTokens", candidate.get("inputOther"))))))
        output_value = as_int(candidate.get("output_tokens", candidate.get("outputTokens", candidate.get("completion_tokens", candidate.get("completionTokens", candidate.get("output"))))))
        cache_value = as_int(candidate.get("cache_read_input_tokens", candidate.get("cacheReadInputTokens", candidate.get("cache_read_tokens", candidate.get("cacheReadTokens", candidate.get("inputCacheRead")))))) or 0
        cache_creation = as_int(candidate.get("inputCacheCreation")) or 0
        if input_value is not None or output_value is not None or cache_value or cache_creation:
            return {
                "input": input_value or 0,
                "output": output_value or 0,
                "cache": cache_value + cache_creation,
            }
    return None


def newest_files(roots: list[Path], patterns: tuple[str, ...] = ("*.jsonl", "*.json"), limit: int = 50) -> list[Path]:
    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    found: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            for path in root.rglob(pattern):
                try:
                    if path.is_file():
                        found.add(path)
                except OSError:
                    # Session files can rotate or disappear while watch scans.
                    continue
    return heapq.nlargest(limit, found, key=mtime)
