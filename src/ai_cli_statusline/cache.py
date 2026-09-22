from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import asdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import RateWindow, Snapshot, as_float, as_int

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows uses the in-process lock
    fcntl = None  # type: ignore[assignment]


_CACHE_WRITE_LOCK = threading.Lock()


def cache_root() -> Path:
    return Path(os.environ.get("AI_CLI_STATUSLINE_HOME", Path.home() / ".ai-cli-statusline")).expanduser()


def _path(provider: str) -> Path:
    return cache_root() / "cache" / f"{provider}.json"


@contextmanager
def _write_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    with _CACHE_WRITE_LOCK, lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_snapshot(snapshot: Snapshot) -> None:
    path = _path(snapshot.provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock(path):
        previous = read_snapshot(snapshot.provider, snapshot.label)
        if previous is not None and not previous.stale:
            snapshot = replace(
                snapshot,
                model=snapshot.model if snapshot.model is not None else previous.model,
                tokens=snapshot.tokens if snapshot.tokens is not None else previous.tokens,
                input_tokens=snapshot.input_tokens if snapshot.input_tokens is not None else previous.input_tokens,
                output_tokens=snapshot.output_tokens if snapshot.output_tokens is not None else previous.output_tokens,
                context_used=snapshot.context_used if snapshot.context_used is not None else previous.context_used,
                context_window=snapshot.context_window if snapshot.context_window is not None else previous.context_window,
                rate_limits=snapshot.rate_limits or previous.rate_limits,
                source=snapshot.source or previous.source,
            )
        payload = asdict(snapshot)
        payload["updated_at"] = snapshot.updated_at.isoformat()
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
                json.dump(payload, handle, ensure_ascii=False)
                temporary = Path(handle.name)
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def _read_snapshot_file(path: Path, provider: str, label: str) -> Snapshot | None:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    raw_limits = payload.get("rate_limits", [])
    if not isinstance(raw_limits, list):
        raw_limits = []
    limits = [RateWindow(str(item.get("label", "")), as_float(item.get("used_percent")), as_float(item.get("resets_at"))) for item in raw_limits if isinstance(item, dict)]
    updated = payload.get("updated_at")
    if not isinstance(updated, str):
        return None
    try:
        updated_at = datetime.fromisoformat(updated)
    except ValueError:
        return None
    snapshot = Snapshot(
        provider=provider,
        label=label,
        maturity=payload.get("maturity") if payload.get("maturity") in {"stable", "experimental", "planned"} else "stable",
        updated_at=updated_at,
        model=payload.get("model") if isinstance(payload.get("model"), str) else None,
        tokens=as_int(payload.get("tokens")),
        input_tokens=as_int(payload.get("input_tokens")),
        output_tokens=as_int(payload.get("output_tokens")),
        context_used=as_int(payload.get("context_used")),
        context_window=as_int(payload.get("context_window")),
        rate_limits=limits,
        source=payload.get("source") if isinstance(payload.get("source"), str) else str(path),
        error=payload.get("error") if isinstance(payload.get("error"), str) else None,
        stale=bool(payload.get("stale", False)),
    )
    if (
        snapshot.model is None
        and snapshot.tokens is None
        and snapshot.context_used is None
        and snapshot.context_window is None
        and not snapshot.rate_limits
    ):
        return None
    return snapshot


def read_snapshot(provider: str, label: str, *, max_age_seconds: float | None = None) -> Snapshot | None:
    snapshot = _read_snapshot_file(_path(provider), provider, label)
    if snapshot is None:
        return None
    if max_age_seconds is None:
        try:
            max_age_seconds = float(os.environ.get("AI_CLI_STATUSLINE_CACHE_TTL_SECONDS", 24 * 60 * 60))
        except ValueError:
            max_age_seconds = 24 * 60 * 60
    updated_at = snapshot.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds()
    if max_age_seconds >= 0 and age > max_age_seconds:
        return replace(snapshot, error="缓存已过期", stale=True)
    return snapshot
