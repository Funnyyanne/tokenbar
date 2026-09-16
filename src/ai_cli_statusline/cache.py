from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import RateWindow, Snapshot, as_float, as_int


def cache_root() -> Path:
    return Path(os.environ.get("AI_CLI_STATUSLINE_HOME", Path.home() / ".ai-cli-statusline")).expanduser()


def _path(provider: str) -> Path:
    return cache_root() / "cache" / f"{provider}.json"


def write_snapshot(snapshot: Snapshot) -> None:
    path = _path(snapshot.provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(snapshot)
    payload["updated_at"] = snapshot.updated_at.isoformat()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def read_snapshot(provider: str, label: str) -> Snapshot | None:
    path = _path(provider)
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    limits = [RateWindow(str(item.get("label", "")), as_float(item.get("used_percent")), as_float(item.get("resets_at"))) for item in payload.get("rate_limits", []) if isinstance(item, dict)]
    updated = payload.get("updated_at")
    try:
        updated_at = datetime.fromisoformat(updated) if isinstance(updated, str) else Snapshot(provider, label).updated_at
    except ValueError:
        updated_at = Snapshot(provider, label).updated_at
    return Snapshot(
        provider=provider,
        label=label,
        updated_at=updated_at,
        model=payload.get("model") if isinstance(payload.get("model"), str) else None,
        tokens=as_int(payload.get("tokens")),
        input_tokens=as_int(payload.get("input_tokens")),
        output_tokens=as_int(payload.get("output_tokens")),
        context_used=as_int(payload.get("context_used")),
        context_window=as_int(payload.get("context_window")),
        rate_limits=limits,
        source=payload.get("source") if isinstance(payload.get("source"), str) else str(path),
    )
