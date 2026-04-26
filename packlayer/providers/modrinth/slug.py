from __future__ import annotations

import re
from pathlib import Path

_MODRINTH_SLUG_RE = re.compile(r"/(?:modpack|mod|plugin|datapack)/([^/?#]+)")
_MRPACK_URL_RE = re.compile(r"https?://")


def is_local(source: str) -> bool:
    return source.endswith(".mrpack") or Path(source).exists()


def is_direct_url(source: str) -> bool:
    return bool(_MRPACK_URL_RE.match(source)) and source.endswith(".mrpack")


def is_modrinth_id(source: str) -> bool:
    return source.startswith("mr:")


def extract_slug(source: str) -> str:
    if source.startswith("mr:"):
        return source[3:]
    match = _MODRINTH_SLUG_RE.search(source)
    if match:
        return match.group(1).rstrip("/")
    return source
