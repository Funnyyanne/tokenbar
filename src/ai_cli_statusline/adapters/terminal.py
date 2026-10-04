from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from .base import Adapter
from .common import newest_files
from .metadata import json_array_metadata, json_metadata, token_count, valid_token_count
from .opencode import OpenCodeAdapter
from .sqlite import SqliteAdapter, SqliteSchema
from ..models import Snapshot, as_float


class SessionMetadataAdapter(Adapter):
    """Provider-specific projections; status follows the newest valid session."""

    maturity = "experimental"
    patterns = ("*.jsonl",)
    fields: dict[str, str] = {}
    lines = True

    def __init__(self, roots: list[Path]) -> None:
        self.roots = roots

    def records(self, path: Path):
        return json_metadata(path, self.fields, lines=self.lines)

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        raise NotImplementedError

    def accepts_path(self, path: Path) -> bool:
        return True

    def session_files(self) -> list[tuple[Path, list[Path]]]:
        return [(path, [path]) for path in newest_files(self.roots, self.patterns)]

    def snapshot(self) -> Snapshot:
        for source, paths in self.session_files():
            observations: dict[object, tuple[int, int, int, str | None]] = {}
            for path in paths:
                if not self.accepts_path(path):
                    continue
                try:
                    for index, row in enumerate(self.records(path)):
                        usage = self.usage(row)
                        if usage is None:
                            continue
                        identity = row.get("id")
                        key = identity if isinstance(identity, str) and identity else (path, index)
                        model = row.get("model")
                        # Rewrites of an observation replace its earlier counters.
                        observations[key] = (*usage, model if isinstance(model, str) else None)
                except OSError:
                    continue
            total = sum(value[2] for value in observations.values())
            if total > 0:
                models = [value[3] for value in observations.values() if value[3]]
                return Snapshot(
                    provider=self.provider, label=self.label, maturity=self.maturity,
                    tokens=total, input_tokens=sum(value[0] for value in observations.values()),
                    output_tokens=sum(value[1] for value in observations.values()),
                    model=models[-1] if models else None, source=str(source),
                )
        return Snapshot.unavailable(self.provider, self.label, "未找到专用格式的 token 元数据", ", ".join(map(str, self.roots)), maturity=self.maturity)


class BuddyAdapter(SessionMetadataAdapter):
    fields = {
        "id": "$.providerData.messageId", "uuid": "$.uuid", "entry_id": "$.id",
        "session": "$.sessionId", "timestamp": "$.timestamp",
        "model": "$.providerData.model", "entry_model": "$.model",
        "input": "$.providerData.rawUsage.prompt_tokens",
        "output": "$.providerData.rawUsage.completion_tokens",
    }

    def records(self, path: Path):
        for row in super().records(path):
            row["id"] = row["id"] or row["uuid"] or row["entry_id"]
            if not row["id"] and row["timestamp"] is not None:
                row["id"] = f"{row['session'] or path.stem}:{row['timestamp']}"
            row["model"] = row["model"] or row["entry_model"]
            yield row

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if not row["id"] or row["input"] is None and row["output"] is None:
            return None
        # prompt/completion already include cache/reasoning subsets.
        input_value, output_value = token_count(row["input"]), token_count(row["output"])
        return input_value, output_value, input_value + output_value


class CodeBuddyAdapter(BuddyAdapter):
    provider, label = "codebuddy", "CodeBuddy"

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("CODEBUDDY_HOME", Path.home() / ".codebuddy")).expanduser()
        super().__init__(roots if roots is not None else [home / "projects"])


class WorkBuddyAdapter(BuddyAdapter):
    provider, label = "workbuddy", "WorkBuddy"

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("WORKBUDDY_HOME", Path.home() / ".workbuddy")).expanduser()
        super().__init__(roots if roots is not None else [home / "projects", home / "traces"])

    @staticmethod
    def _modified(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0

    @staticmethod
    def _main_path(path: Path) -> Path:
        for parent in path.parents:
            if parent.name == "subagents":
                session = parent.parent
                return session.with_name(session.name + ".jsonl")
        return path

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        input_value, output_value = valid_token_count(row["input"]), valid_token_count(row["output"])
        if not isinstance(row["id"], str) or not row["id"] or input_value is None or output_value is None:
            return None
        return input_value, output_value, input_value + output_value

    def _details(self, main: Path, paths: list[Path]) -> tuple[Snapshot | None, set[str]]:
        observations = {}
        sessions = set()
        for path in sorted(paths, key=self._modified):
            try:
                for row in self.records(path):
                    usage = self.usage(row)
                    if usage is None:
                        continue
                    session = row["session"]
                    if isinstance(session, str) and session:
                        sessions.add(session)
                    model = row["model"] if isinstance(row["model"], str) else None
                    observations[row["id"]] = (*usage, model)
            except OSError:
                continue
        if observations:
            sessions.add(main.stem)
        total = sum(row[2] for row in observations.values())
        if not total:
            return None, sessions
        models = [row[3] for row in observations.values() if row[3]]
        source = main if main.is_file() else max(paths, key=self._modified)
        return Snapshot(provider=self.provider, label=self.label, maturity=self.maturity,
            tokens=total, input_tokens=sum(row[0] for row in observations.values()),
            output_tokens=sum(row[1] for row in observations.values()),
            model=models[-1] if models else None, source=str(source)), sessions

    def _trace(self, path: Path) -> tuple[str, Snapshot] | None:
        fields = {"id": "$.trace.traceId", "session": "$.trace.sessionId", "meta_session": "$.trace.metadata.sessionId",
            "started": "$.trace.startedAt", "meta_started": "$.trace.metadata.startedAt"}
        for prefix, base in (("root", "$.trace.modelInfo"), ("meta", "$.trace.metadata.modelInfo")):
            for name, field in (("input", "totalInputTokens"), ("output", "totalOutputTokens"),
                ("first_model", "models[0]"), ("model", "model")):
                fields[prefix + "_" + name] = base + "." + field
        try:
            for row in json_metadata(path, fields, lines=False, types={"root_type": "$.trace.modelInfo"}):
                prefix = "root" if row["root_type"] == "object" else "meta"
                input_value = valid_token_count(row[prefix + "_input"])
                output_value = valid_token_count(row[prefix + "_output"])
                if input_value is None or output_value is None or not input_value + output_value:
                    continue
                started = row["started"] or row["meta_started"]
                timestamp = as_float(started) if isinstance(started, (int, float)) else None
                if isinstance(started, str):
                    try:
                        timestamp = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
                    except (ValueError, OverflowError, OSError):
                        continue
                if timestamp is None or timestamp <= 0:
                    continue
                session = next((row[key] for key in ("session", "meta_session", "id")
                    if isinstance(row[key], str) and row[key]), path.stem)
                model = row[prefix + "_first_model"] or row[prefix + "_model"]
                # These are inclusive totals; totalCachedTokens is not added again.
                return session, Snapshot(provider=self.provider, label=self.label, maturity=self.maturity,
                    tokens=input_value + output_value, input_tokens=input_value, output_tokens=output_value,
                    model=model if isinstance(model, str) and model else "auto", source=str(path))
        except OSError:
            pass
        return None

    def snapshot(self) -> Snapshot:
        groups = {}
        for path in newest_files(self.roots, ("*.jsonl",)):
            groups.setdefault(self._main_path(path), []).append(path)
        candidates = []
        detailed_sessions = set()
        for main, paths in groups.items():
            snapshot, sessions = self._details(main, paths)
            detailed_sessions.update(sessions)
            if snapshot is not None:
                candidates.append((max(map(self._modified, paths)), snapshot))
        traced_sessions = set()
        for path in newest_files(self.roots, ("trace_*.json",)):
            result = self._trace(path)
            if result is None:
                continue
            session, snapshot = result
            if session in detailed_sessions or session in traced_sessions:
                continue
            traced_sessions.add(session)
            candidates.append((self._modified(path), snapshot))
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
        return Snapshot.unavailable(self.provider, self.label,
            "未找到 WorkBuddy 明确 JSONL／trace token 元数据；SQLite context／credits 不计 token",
            ", ".join(map(str, self.roots)), maturity=self.maturity)


class PiMetadataAdapter(SessionMetadataAdapter):
    fields = {
        "type": "$.type", "id": "$.id", "role": "$.message.role",
        "model": "$.message.model", "backend": "$.message.provider",
        "input": "$.message.usage.input", "output": "$.message.usage.output",
        "cache_read": "$.message.usage.cacheRead", "cache_write": "$.message.usage.cacheWrite",
        "reasoning": "$.message.usage.reasoningTokens", "reasoning_alt": "$.message.usage.reasoning",
        "total": "$.message.usage.totalTokens",
    }

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if row["role"] != "assistant" or self.provider != "minimax" and row["type"] != "message":
            return None
        backend = row["backend"].strip().lower() if isinstance(row["backend"], str) else None
        if self.provider == "dots" and backend != "dots" or self.provider == "pi" and backend == "dots":
            return None
        input_value = token_count(row["input"]) + token_count(row["cache_read"]) + token_count(row["cache_write"])
        output_value = token_count(row["output"])
        if self.provider != "omo":
            output_value += token_count(row["reasoning"])
        total = token_count(row["total"]) or input_value + output_value
        return input_value, output_value, total


class PiTreeAdapter(PiMetadataAdapter):
    """OMP/OmO persist nested transcripts beside their main session file."""

    def session_files(self) -> list[tuple[Path, list[Path]]]:
        paths = newest_files(self.roots, self.patterns)
        known = set(paths)
        groups: dict[Path, list[Path]] = {}
        for path in reversed(paths):
            main = path
            for root in self.roots:
                if root.name != "sessions" or not path.is_relative_to(root):
                    continue
                parts = path.relative_to(root).parts
                if len(parts) > 2:
                    main = root / parts[0] / (parts[1] + ".jsonl")
                    break
            # Use the outermost main transcript already inside the scan roots.
            if main == path:
                for parent in path.parents:
                    candidate = parent.with_name(parent.name + ".jsonl") if parent.name else parent
                    if candidate in known:
                        main = candidate
            groups.setdefault(main, []).append(path)
        # Insertion order of each group follows oldest-to-newest file mtime.
        order = {path: index for index, path in enumerate(paths)}
        sessions = [(main if main in known else files[-1], files) for main, files in groups.items()]
        return sorted(sessions, key=lambda item: min(order[path] for path in item[1]))

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        fields = ("input", "output", "cache_read", "cache_write", "total")
        if self.provider == "omp":
            fields += ("reasoning",)
        if any(row[key] is not None and valid_token_count(row[key]) is None for key in fields):
            return None
        return super().usage(row)


class OmoAdapter(PiTreeAdapter):
    provider, label = "omo", "OmO"

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("OMO_HOME", Path.home() / ".omo")).expanduser()
        super().__init__(roots if roots is not None else [home / "agent" / "sessions"])


class DotsAdapter(PiMetadataAdapter):
    provider, label = "dots", "Dots"

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(roots if roots is not None else [Path.home() / ".pi" / "agent" / "sessions"])


class PrimeAdapter(PiMetadataAdapter):
    provider, label = "prime", "Prime Agent"

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(roots if roots is not None else [Path.home() / ".prime" / "agent" / "sessions"])


class MiniMaxAdapter(PiMetadataAdapter):
    provider, label = "minimax", "MiniMax Code"
    patterns = ("messages.jsonl",)
    fields = {**PiMetadataAdapter.fields, "id": "$.message_id"}

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(roots if roots is not None else [Path.home() / ".minimax" / "v2" / "sessions"])

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        return super().usage(row) if row["id"] else None


class CommandCodeAdapter(SessionMetadataAdapter):
    provider, label = "commandcode", "Command Code"
    fields = {
        "type": "$.type", "id": "$.id", "model": "$.model",
        "input": "$.usage.inputTokens", "output": "$.usage.outputTokens",
    }

    def __init__(self, roots: list[Path] | None = None) -> None:
        super().__init__(roots if roots is not None else [Path.home() / ".commandcode" / "projects"])

    def accepts_path(self, path: Path) -> bool:
        return not path.name.endswith(".checkpoints.jsonl") and ".prompts." not in path.name

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if row["type"] != "message" or not row["id"] or row["input"] is None and row["output"] is None:
            return None
        input_value, output_value = token_count(row["input"]), token_count(row["output"])
        return input_value, output_value, input_value + output_value


class ReasonixAdapter(SessionMetadataAdapter):
    provider, label = "reasonix", "Reasonix"
    patterns = ("*.jsonl.telemetry.json",)
    lines = False
    fields = {"input": "$.usage.promptTokens", "output": "$.usage.completionTokens"}

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("REASONIX_STATE_HOME", Path.home() / ".reasonix")).expanduser()
        defaults = [home]
        if os.name == "nt" and os.environ.get("APPDATA"):
            defaults.append(Path(os.environ["APPDATA"]) / "reasonix")
        super().__init__(roots if roots is not None else defaults)

    def records(self, path: Path):
        meta_path = Path(str(path).removesuffix(".telemetry.json") + ".meta")
        try:
            meta = next(json_metadata(meta_path, {"model": "$.model"}, lines=False), {})
        except OSError:
            meta = {}
        for row in super().records(path):
            yield {**row, "model": meta.get("model")}

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if row["input"] is None and row["output"] is None:
            return None
        # Telemetry is cumulative; cache and reasoning are subsets.
        input_value, output_value = token_count(row["input"]), token_count(row["output"])
        return input_value, output_value, input_value + output_value


class MimoAdapter(OpenCodeAdapter):
    """MiMo's OpenCode schema, restricted to native MiMo provider turns."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")).expanduser()
        super().__init__(roots if roots is not None else [data_home / "mimocode"])
        self.provider, self.label, self.maturity = "mimo", "MiMo", "experimental"
        self.patterns = ("mimocode.db",)
        # Session aggregates include mirrored Claude history; use message usage.
        self.schemas = ()

    def _legacy_filter(self) -> str:
        return "AND lower(COALESCE(json_extract(data, '$.providerID'), json_extract(data, '$.model.providerID'), '')) IN ('mimo', 'xiaomi')"


class OpenClawAdapter(PiMetadataAdapter):
    provider, label = "openclaw", "OpenClaw"

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("OPENCLAW_STATE_DIR", Path.home() / ".openclaw")).expanduser()
        super().__init__(roots if roots is not None else [home / "agents"])

    def accepts_path(self, path: Path) -> bool:
        return path.parent.name == "sessions"

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if row["type"] != "message" or row["role"] != "assistant":
            return None
        input_value = max(token_count(row["input"]), token_count(row["cache_read"])) + token_count(row["cache_write"])
        output_value = token_count(row["output"])
        return input_value, output_value, token_count(row["total"]) or input_value + output_value


class DroidAdapter(SessionMetadataAdapter):
    provider, label = "droid", "Droid"
    patterns = ("*.settings.json",)
    lines = False
    fields = {
        "model": "$.model", "input": "$.tokenUsage.inputTokens", "output": "$.tokenUsage.outputTokens",
        "cache_read": "$.tokenUsage.cacheReadTokens", "cache_write": "$.tokenUsage.cacheCreationTokens",
        "reasoning": "$.tokenUsage.thinkingTokens", "total": "$.tokenUsage.totalTokens",
    }

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("FACTORY_DIR", Path.home() / ".factory")).expanduser()
        super().__init__(roots if roots is not None else [home / "sessions"])

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        input_value = token_count(row["input"]) + token_count(row["cache_read"]) + token_count(row["cache_write"])
        output_value = token_count(row["output"]) + token_count(row["reasoning"])
        total = token_count(row["total"]) or input_value + output_value
        return input_value, output_value, total


class HermesAdapter(SqliteAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
        super().__init__("hermes", roots if roots is not None else [home], schemas=(SqliteSchema(
            table="sessions", input_columns=("input_tokens",), output_columns=("output_tokens", "reasoning_tokens"),
            cache_columns=("cache_read_tokens", "cache_write_tokens"), model_column="model",
        ),), patterns=("state.db",), maturity="experimental")
        self.label = "Hermes"


class ClaudeScienceAdapter(SqliteAdapter):
    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("CLAUDE_SCIENCE_HOME", Path.home() / ".claude-science")).expanduser()
        super().__init__("claudescience", roots if roots is not None else [home], schemas=(SqliteSchema(
            table="frames", input_columns=("input_tokens", "aux_input_tokens"),
            output_columns=("output_tokens", "aux_output_tokens"), model_column="model",
        ),), patterns=("operon-cli.db", "operon.db"), maturity="experimental")
        # input counters already include cache. Demo context_data is excluded.
        self.label = "Claude Science"

    def _read_schema(self, connection, schema):
        columns = {row[1] for row in connection.execute('PRAGMA table_info("frames")')}
        fields = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
            "aux_input_tokens", "aux_output_tokens", "aux_cache_read_tokens", "aux_cache_write_tokens", "model")
        if not columns.intersection(fields[:-1]):
            return None
        selected = ", ".join(f'"{name}"' if name in columns else "NULL" for name in fields)
        input_total = output_total = 0
        model = None
        for values in connection.execute(f'SELECT {selected} FROM frames'):
            main_in, main_out, main_read, main_write, aux_in, aux_out, aux_read, aux_write = map(token_count, values[:8])
            input_value = max(main_in, main_read + main_write) + max(aux_in, aux_read + aux_write)
            output_value = main_out + aux_out
            if not input_value + output_value:
                continue
            input_total += input_value
            output_total += output_value
            if isinstance(values[8], str) and values[8]:
                model = values[8]
        total = input_total + output_total
        return (total, input_total, output_total, model) if total else None


class ClineAdapter(SessionMetadataAdapter):
    provider, label = "cline", "Cline"
    patterns = ("*.messages.json",)
    fields = {"id": "$.id", "timestamp": "$.ts", "role": "$.role", "model": "$.modelInfo.id",
        "input": "$.metrics.inputTokens", "output": "$.metrics.outputTokens"}

    def __init__(self, roots: list[Path] | None = None) -> None:
        if os.environ.get("CLINE_SESSION_DATA_DIR"):
            defaults = [Path(os.environ["CLINE_SESSION_DATA_DIR"]).expanduser()]
        elif os.environ.get("CLINE_DATA_DIR"):
            defaults = [Path(os.environ["CLINE_DATA_DIR"]).expanduser() / "sessions"]
        else:
            defaults = [Path(os.environ.get("CLINE_DIR", Path.home() / ".cline")).expanduser() / "data" / "sessions"]
        super().__init__(roots if roots is not None else defaults)

    def records(self, path: Path):
        meta_path = path.with_name(path.parent.name + ".json")
        try:
            meta = next(json_metadata(meta_path, {"model": "$.model", "imported": "$.metadata.importedFrom.importedAt"}, lines=False), {})
        except OSError:
            meta = {}
        imported_at = None
        if isinstance(meta.get("imported"), str):
            try:
                imported_at = datetime.fromisoformat(meta["imported"].replace("Z", "+00:00")).timestamp() * 1000
            except ValueError:
                pass
        for row in json_array_metadata(path, self.fields):
            if imported_at is not None and token_count(row["timestamp"]) <= imported_at:
                continue
            row["model"] = row["model"] or meta.get("model")
            yield row

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if row["role"] != "assistant" or row["input"] is None and row["output"] is None:
            return None
        input_value, output_value = token_count(row["input"]), token_count(row["output"])
        return input_value, output_value, input_value + output_value


class CodexRolloutAdapter(SessionMetadataAdapter):
    fields = {"type": "$.type", "event": "$.payload.type", "model": "$.payload.model",
        "input": "$.payload.info.total_token_usage.input_tokens",
        "output": "$.payload.info.total_token_usage.output_tokens",
        "total": "$.payload.info.total_token_usage.total_tokens"}

    def records(self, path: Path):
        model = None
        for row in super().records(path):
            if row["type"] == "turn_context" and isinstance(row["model"], str):
                model = row["model"]
            if row["type"] == "event_msg" and row["event"] == "token_count":
                # Each event replaces the session's cumulative snapshot.
                yield {**row, "id": "session-total", "model": model}

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if row["input"] is None and row["output"] is None and row["total"] is None:
            return None
        input_value, output_value = token_count(row["input"]), token_count(row["output"])
        return input_value, output_value, token_count(row["total"]) or input_value + output_value


class AStudioAdapter(CodexRolloutAdapter):
    provider, label = "astudio", "AStudio"

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path.home() / ".acode"
        super().__init__(roots if roots is not None else [home / "sessions", home / "archived_sessions"])


class EveryCodeAdapter(CodexRolloutAdapter):
    provider, label = "everycode", "Every Code"

    def __init__(self, roots: list[Path] | None = None) -> None:
        home = Path(os.environ.get("CODE_HOME", Path.home() / ".code")).expanduser()
        super().__init__(roots if roots is not None else [home / "sessions"])


class QoderAdapter(SessionMetadataAdapter):
    provider, label = "qoder", "Qoder"
    fields = {"type": "$.type", "role": "$.message.role", "id": "$.message.id",
        "uuid": "$.uuid", "model": "$.message.model", "input": "$.message.usage.input_tokens",
        "output": "$.message.usage.output_tokens", "cache_read": "$.message.usage.cache_read_input_tokens",
        "cached": "$.message.usage.cached_tokens", "cache_write": "$.message.usage.cache_creation_input_tokens"}

    def __init__(self, roots: list[Path] | None = None) -> None:
        root = Path(os.environ.get("QODER_PROJECTS_DIR", Path.home() / ".qoder" / "projects")).expanduser()
        super().__init__(roots if roots is not None else [root])

    def records(self, path: Path):
        for row in super().records(path):
            row["id"] = row["id"] or row["uuid"]
            yield row

    def usage(self, row: dict) -> tuple[int, int, int] | None:
        if row["type"] != "assistant" or row["role"] != "assistant":
            return None
        cache_read = row["cache_read"] if row["cache_read"] is not None else row["cached"]
        input_value = token_count(row["input"]) + token_count(cache_read) + token_count(row["cache_write"])
        output_value = token_count(row["output"])
        return input_value, output_value, input_value + output_value


class QoderCNAdapter(QoderAdapter):
    provider, label = "qodercn", "Qoder CN"

    def __init__(self, roots: list[Path] | None = None) -> None:
        root = Path(os.environ.get("QODER_CN_PROJECTS_DIR", Path.home() / ".qoder-cn" / "projects")).expanduser()
        super().__init__(roots if roots is not None else [root])
