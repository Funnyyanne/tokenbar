from .base import Adapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .cursor import CursorAdapter
from .generic import GenericCliAdapter
from .kimi import KimiAdapter
from .opencode import OpenCodeAdapter
from .sqlite import SqliteAdapter, SqliteSchema
from .unavailable import UnavailableAdapter
from .grok import GrokAdapter
from .deepseek import DeepSeekAdapter
from .lmstudio import LMStudioAdapter
from .antigravity import AntigravityAdapter
from .kiro import KiroAdapter
from .terminal import (
    CodeBuddyAdapter, CommandCodeAdapter, DotsAdapter, MiniMaxAdapter,
    MimoAdapter, OmoAdapter, PrimeAdapter, ReasonixAdapter, WorkBuddyAdapter,
    ClaudeScienceAdapter, ClineAdapter, DroidAdapter, HermesAdapter, OpenClawAdapter,
    AStudioAdapter, EveryCodeAdapter, QoderAdapter, QoderCNAdapter,
)
from .experimental import (
    AnythingLLMAdapter, CopilotAdapter, DevinAdapter, GeminiAdapter, GooseAdapter,
    KiloAdapter, OmpAdapter, PiAdapter, RooAdapter, ZCodeAdapter, ZedAdapter,
)

__all__ = [
    "Adapter",
    "ClaudeAdapter",
    "CodexAdapter",
    "CursorAdapter",
    "GenericCliAdapter",
    "KimiAdapter",
    "OpenCodeAdapter",
    "SqliteAdapter",
    "SqliteSchema",
    "UnavailableAdapter",
    "GrokAdapter",
    "DeepSeekAdapter",
    "LMStudioAdapter",
    "AntigravityAdapter",
    "KiroAdapter",
    "AnythingLLMAdapter",
    "CopilotAdapter",
    "DevinAdapter",
    "GeminiAdapter",
    "GooseAdapter",
    "KiloAdapter",
    "OmpAdapter",
    "PiAdapter",
    "RooAdapter",
    "ZCodeAdapter",
    "ZedAdapter",
    "CodeBuddyAdapter",
    "WorkBuddyAdapter",
    "OmoAdapter",
    "DotsAdapter",
    "PrimeAdapter",
    "MiniMaxAdapter",
    "CommandCodeAdapter",
    "ReasonixAdapter",
    "MimoAdapter",
    "ClaudeScienceAdapter",
    "ClineAdapter",
    "DroidAdapter",
    "HermesAdapter",
    "OpenClawAdapter",
    "AStudioAdapter",
    "EveryCodeAdapter",
    "QoderAdapter",
    "QoderCNAdapter",
]
