from __future__ import annotations

import re

_FTB_URL_RE = re.compile(
    r"https?://(?:www\.)?feed-the-beast\.com/modpacks/[^/?#]+-(\d+)"
)
_FTB_ID_RE = re.compile(r"^ftb:(\d+)$")


def is_ftb_url(source: str) -> bool:
    return bool(_FTB_URL_RE.match(source))


def is_ftb_id(source: str) -> bool:
    return bool(_FTB_ID_RE.match(source))


def extract_id(source: str) -> int:
    match = _FTB_URL_RE.search(source) or _FTB_ID_RE.match(source)
    if match:
        return int(match.group(1))
    raise ValueError(f"cannot extract FTB pack ID from: {source!r}")
