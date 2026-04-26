from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class HttpClient(ABC):
    @abstractmethod
    async def get_json(
        self,
        url: str,
        params: dict | None = None,
        headers: dict[str, str] | None = None,
        json: dict | None = None,
    ) -> Any: ...

    @abstractmethod
    async def get_bytes(self, url: str) -> bytes: ...

    # Intentionally non-async: async generators are plain callables that return
    # an AsyncIterator — no await needed at the call site. Making this `async def`
    # would tell type checkers it's a coroutine, breaking `async for` iteration.
    @abstractmethod
    def get_stream(self, url: str) -> AsyncIterator[bytes]: ...
