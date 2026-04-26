from __future__ import annotations

from typing import Union, Callable, Awaitable


type MinecraftVersion = str
type ProgressCallback = Union[
    Callable[[], None],
    Callable[[], Awaitable[None]],
]
