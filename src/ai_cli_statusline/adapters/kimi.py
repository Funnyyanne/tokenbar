from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .base import Adapter
from .common import iter_json_objects, newest_files, usage_from_object
from ..models import Snapshot, as_int


class KimiAdapter(Adapter):
    provider = "kimi"
    label = "Kimi"

    def __init__(self, roots: list[Path] | None = None, max_bytes: int = 4 * 1024 * 1024) -> None:
        configured = os.environ.get("KIMI_CONFIG_DIR")
        self.roots = roots or ([Path(configured)] if configured else [Path.home() / ".kimi", Path.home() / ".config" / "kimi"])
        self.max_bytes = max_bytes

    def snapshot(self) -> Snapshot:
        files = newest_files(self.roots)
        if not files:
            return Snapshot.unavailable(self.provider, self.label, "未找到 Kimi 会话日志", ", ".join(map(str, self.roots)))
        path = files[0]
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
                        candidate_model = obj.get("model")
                        if isinstance(candidate_model, str) and candidate_model:
                            model = candidate_model
                        context_used = as_int(obj.get("context_used", obj.get("contextUsed"))) or context_used
                        context_window = as_int(obj.get("context_window", obj.get("contextWindow"))) or context_window
        except OSError as exc:
            return Snapshot.unavailable(self.provider, self.label, f"日志读取失败：{exc}", str(path))
        total = totals["input"] + totals["output"] + totals["cache"]
        if total == 0:
            return Snapshot.unavailable(self.provider, self.label, "日志中没有可识别 token 字段", str(path))
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
