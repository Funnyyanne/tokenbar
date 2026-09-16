from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .base import Adapter
from .common import iter_json_objects, newest_files, usage_from_object
from ..cache import read_snapshot
from ..models import Snapshot, as_int


class JsonlAdapter(Adapter):
    """Read the newest session containing usage data without reading prompt bodies."""

    def __init__(self, provider: str, label: str, roots: list[Path], patterns: tuple[str, ...] = ("*.jsonl", "*.json"), max_bytes: int = 8 * 1024 * 1024) -> None:
        self.provider = provider
        self.label = label
        self.roots = roots
        self.patterns = patterns
        self.max_bytes = max_bytes

    def _read_file(self, path: Path) -> Snapshot | None:
        totals = {"input": 0, "output": 0, "cache": 0}
        model: str | None = None
        context_used: int | None = None
        context_window: int | None = None
        try:
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - self.max_bytes))
                if handle.tell():
                    handle.readline()
                for raw in handle:
                    try:
                        value: Any = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    for obj in iter_json_objects(value):
                        usage = usage_from_object(obj)
                        if usage:
                            for key in totals:
                                totals[key] += usage[key]
                        candidate_model = obj.get("model") or obj.get("model_name") or obj.get("modelName")
                        if isinstance(candidate_model, str) and candidate_model:
                            model = candidate_model
                        context_used = as_int(obj.get("context_used", obj.get("contextUsed"))) or context_used
                        context_window = as_int(obj.get("context_window", obj.get("contextWindow"))) or context_window
        except OSError:
            return None
        total = totals["input"] + totals["output"] + totals["cache"]
        if total == 0:
            return None
        return Snapshot(
            provider=self.provider,
            label=self.label,
            model=model,
            tokens=total,
            input_tokens=totals["input"] + totals["cache"],
            output_tokens=totals["output"],
            context_used=context_used,
            context_window=context_window,
            source=str(path),
        )

    def snapshot(self) -> Snapshot:
        for path in newest_files(self.roots, self.patterns):
            snapshot = self._read_file(path)
            if snapshot is not None:
                return snapshot
        cached = read_snapshot(self.provider, self.label)
        if cached is not None:
            return cached
        return Snapshot.unavailable(self.provider, self.label, "未找到可识别 token 字段", ", ".join(map(str, self.roots)))


def configured_roots(env_name: str, defaults: list[Path]) -> list[Path]:
    configured = os.environ.get(env_name)
    return [Path(configured).expanduser()] if configured else defaults
