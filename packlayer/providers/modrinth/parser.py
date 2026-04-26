from __future__ import annotations

import json
from typing import Literal
import zipfile
from io import BytesIO
from pathlib import Path

from packlayer.domain.exceptions import InvalidMrpack
from packlayer.domain.models import ModFile, Modpack, Override

_INDEX = "modrinth.index.json"


def extract_index(raw: bytes) -> tuple[dict, zipfile.ZipFile]:
    zf = zipfile.ZipFile(BytesIO(raw))
    if _INDEX not in zf.namelist():
        raise ValueError(f"missing {_INDEX} in mrpack")

    with zf.open(_INDEX) as f:
        return json.load(f), zf


def parse_modpack(index: dict, zf: zipfile.ZipFile) -> Modpack:
    try:
        files = tuple(
            ModFile(
                url=entry["downloads"][0],
                filename=Path(entry["path"]).name,
                side=_parse_side(entry.get("env", {})),
                optional=entry.get("env", {}).get("client") == "optional",
                size=entry["fileSize"],
                hash=entry["hashes"]["sha512"],
                hash_type="sha512",
            )
            for entry in index.get("files", [])
            if entry.get("downloads")
        )
        overrides = _extract_overrides(zf)
        return Modpack(
            name=index["name"],
            version=index["versionId"],
            minecraft_version=index["dependencies"]["minecraft"],
            files=files,
            overrides=overrides,
        )
    except (KeyError, IndexError) as e:
        raise InvalidMrpack(f"malformed index: {e}") from e


def _extract_overrides(zf: zipfile.ZipFile) -> tuple[Override, ...]:
    result = []
    side: Literal["client", "server", "both"]
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        if name.startswith("overrides/"):
            path, side = name.removeprefix("overrides/"), "both"
        elif name.startswith("client-overrides/"):
            path, side = name.removeprefix("client-overrides/"), "client"
        elif name.startswith("server-overrides/"):
            path, side = name.removeprefix("server-overrides/"), "server"
        else:
            continue
        result.append(Override(path=path, data=zf.read(name), side=side))
    return tuple(result)


def _parse_side(env: dict) -> Literal["client", "server", "both"]:
    client = env.get("client", "required")
    server = env.get("server", "required")
    if client == "unsupported":
        return "server"

    if server == "unsupported":
        return "client"

    return "both"
