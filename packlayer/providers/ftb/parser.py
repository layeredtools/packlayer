# providers/ftb/parser.py
from __future__ import annotations

import logging
from typing import Literal

from packlayer.domain.exceptions import InvalidMrpack
from packlayer.domain.models import ModFile, Modpack, Override

logger = logging.getLogger("packlayer.ftb.parser")


def parse_modpack(pack: dict, version: dict) -> Modpack:
    """
    Build a [`Modpack`][Modpack] from FTB API responses.

    Args:
        pack: Response from ``GET /public/modpack/{packId}``.
        version: Response from ``GET /public/modpack/{packId}/{versionId}``.

    Raises:
        InvalidMrpack: Either response is missing required fields.
    """
    try:
        name: str = pack["name"]
        version_number: str = version["name"]
        minecraft_version: str = _extract_minecraft_version(version)

        files = []
        overrides = []

        for f in version.get("files", []):
            if f.get("serveronly", False):
                continue

            side = _parse_side(f)
            directory: str = f.get("path", "")
            filename: str = f["name"]
            full_path = f"{directory}/{filename}" if directory else filename

            if filename.endswith(".jar") or f.get("url", "").endswith(".jar"):
                files.append(_parse_file(f, side))
            else:
                overrides.append(_parse_override(f, full_path, side))

    except KeyError as e:
        raise InvalidMrpack(f"malformed FTB API response: {e}") from e

    return Modpack(
        name=name,
        version=version_number,
        minecraft_version=minecraft_version,
        files=tuple(files),
        overrides=tuple(overrides),
    )


def _extract_minecraft_version(version: dict) -> str:
    for target in version.get("targets", []):
        if target.get("type") == "game":
            return target["version"]
    raise KeyError("minecraft version not found in targets")


def _curseforge_url(f: dict) -> str | None:
    cf = f.get("curseforge")
    if not cf:
        return None
    file_id = str(cf["file"])
    return f"https://edge.forgecdn.net/files/{file_id[:-3]}/{file_id[-3:]}/{f['name']}"


def _parse_file(f: dict, side: Literal["client", "server", "both"]) -> ModFile:
    url = f.get("url") or _curseforge_url(f) or ""
    return ModFile(
        url=url,
        filename=f["name"],
        size=f.get("size", 0),
        hash=f.get("sha1"),
        hash_type="sha1" if f.get("sha1") else None,
        optional=f.get("optional", False),
        side=side,
    )


def _parse_override(
    f: dict,
    path: str,
    side: Literal["client", "server", "both"],
) -> Override:
    return Override(
        path=path,
        url=f["url"],
        side=side,
    )


def _parse_side(f: dict) -> Literal["client", "server", "both"]:
    if f.get("clientonly"):
        return "client"

    if f.get("serveronly"):
        return "server"

    return "both"
