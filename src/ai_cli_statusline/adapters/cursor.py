from __future__ import annotations

from pathlib import Path

from .unavailable import UnavailableAdapter


class CursorAdapter(UnavailableAdapter):
    """Declare Cursor's privacy boundary until a credential-free source exists."""

    provider = "cursor"
    label = "Cursor"

    def __init__(self, roots: tuple[Path, ...] | None = None) -> None:
        roots = roots or (
            Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage",
            Path.home() / ".config" / "Cursor" / "User" / "globalStorage",
        )
        super().__init__(
            self.provider,
            self.label,
            roots,
            "experimental",
            "隐私限制：已知用量方案需要读取认证 token 并调用远端接口，本工具不会这样做",
        )
