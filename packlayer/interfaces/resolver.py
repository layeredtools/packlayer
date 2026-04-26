from __future__ import annotations

from abc import ABC, abstractmethod

from packlayer.domain.models import Modpack, ModpackVersion


class ModpackResolver(ABC):
    @abstractmethod
    def can_handle(self, source: str) -> bool: ...

    @abstractmethod
    async def resolve(
        self, source: str, *, modpack_version: str | None = None
    ) -> Modpack: ...

    @abstractmethod
    async def fetch_versions(self, source: str) -> list[ModpackVersion]: ...
