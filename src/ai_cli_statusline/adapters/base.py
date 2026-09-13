from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Snapshot


class Adapter(ABC):
    provider: str
    label: str

    @abstractmethod
    def snapshot(self) -> Snapshot:
        raise NotImplementedError
