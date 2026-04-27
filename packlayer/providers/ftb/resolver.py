# providers/ftb/resolver.py
from __future__ import annotations

import logging

from datetime import datetime, timezone
from packlayer.domain.exceptions import (
    NetworkError,
    NoVersionFound,
    SlugNotFound,
)
from packlayer.domain.models import Modpack, ModpackVersion
from packlayer.interfaces.http import HttpClient
from packlayer.interfaces.resolver import ModpackResolver
from packlayer.providers.ftb.parser import parse_modpack
from packlayer.providers.ftb.slug import extract_id, is_ftb_id, is_ftb_url
from packlayer.types import MinecraftVersion

logger = logging.getLogger("packlayer.ftb")

_API = "https://api.modpacks.ch/public"


class FTBResolver(ModpackResolver):
    """
    Resolves FTB modpacks from feed-the-beast.com URLs or prefixed IDs (``ftb:<id>``).

    No API key required.

    Args:
        http: Async HTTP client for API calls.
        minecraft_version: If provided, filters version listings to only
            include releases compatible with this Minecraft version.
    """

    def __init__(
        self,
        http: HttpClient,
        minecraft_version: MinecraftVersion | None = None,
    ) -> None:
        self._http = http
        self._minecraft_version = minecraft_version

    def can_handle(self, source: str) -> bool:
        return is_ftb_url(source) or is_ftb_id(source)

    async def resolve(
        self, source: str, *, modpack_version: str | None = None
    ) -> Modpack:
        """
        Resolve a modpack from an FTB URL or prefixed pack ID.

        Args:
            source: A ``feed-the-beast.com/modpacks/`` URL or ``ftb:<id>``.
            modpack_version: If provided, resolves this specific version name
                instead of the latest. Must match a version ``name`` field
                from the API (e.g. ``"1.8.0"``).

        Raises:
            SlugNotFound: No FTB pack matches the given ID.
            NoVersionFound: The pack exists but has no compatible version,
                or ``modpack_version`` was specified but not found.
            NetworkError: A network failure occurred.
        """
        pack_id = extract_id(source)
        pack, version = await self._fetch_version_for(pack_id, modpack_version)
        return parse_modpack(pack, version)

    async def fetch_versions(self, source: str) -> list[ModpackVersion]:
        """
        Return all available versions of an FTB modpack, newest-first.

        Args:
            source: A ``feed-the-beast.com/modpacks/`` URL or ``ftb:<id>``.

        Returns:
            A list of [`ModpackVersion`][ModpackVersion] objects.

        Raises:
            SlugNotFound: No FTB pack matches the given ID.
            NoVersionFound: No compatible versions found.
            NetworkError: A network failure occurred.
        """
        pack_id = extract_id(source)
        pack = await self._fetch_pack(pack_id)
        versions = self._filter_versions(pack.get("versions", []))

        if not versions:
            raise NoVersionFound(str(pack_id), self._minecraft_version)

        return [_parse_version(v) for v in reversed(versions)]

    async def _fetch_version_for(
        self, pack_id: int, modpack_version: str | None
    ) -> tuple[dict, dict]:
        pack = await self._fetch_pack(pack_id)
        versions = self._filter_versions(pack.get("versions", []))

        if not versions:
            raise NoVersionFound(str(pack_id), self._minecraft_version)

        if modpack_version is not None:
            match = next((v for v in versions if v["name"] == modpack_version), None)
            if match is None:
                raise NoVersionFound(str(pack_id), self._minecraft_version)
            raw_version = match
        else:
            raw_version = versions[-1]  # FTB returns oldest-first

        logger.debug(
            f"resolving FTB version: {raw_version['name']} (id={raw_version['id']})"
        )
        version = await self._fetch_version(pack_id, raw_version["id"])
        return pack, version

    def _filter_versions(self, versions: list[dict]) -> list[dict]:
        if not self._minecraft_version:
            return versions
        return [
            v
            for v in versions
            if any(
                t.get("type") == "game" and t.get("version") == self._minecraft_version
                for t in v.get("targets", [])
            )
        ]

    async def _fetch_pack(self, pack_id: int) -> dict:
        try:
            return await self._http.get_json(f"{_API}/modpack/{pack_id}")
        except NetworkError as e:
            if "404" in str(e):
                raise SlugNotFound(str(pack_id)) from e
            raise

    async def _fetch_version(self, pack_id: int, version_id: int) -> dict:
        try:
            return await self._http.get_json(f"{_API}/modpack/{pack_id}/{version_id}")
        except NetworkError as e:
            if "404" in str(e):
                raise NoVersionFound(str(pack_id), self._minecraft_version) from e
            raise


def _parse_version(raw: dict) -> ModpackVersion:
    mc_version = ""
    for target in raw.get("targets", []):
        if target.get("type") == "game":
            mc_version = target.get("version", "")
            break

    loaders = tuple(
        target["name"].lower()
        for target in raw.get("targets", [])
        if target.get("type") == "modloader"
    )

    updated = raw.get("updated")
    if updated:
        # normalizes to ISO 8601
        date_published = datetime.fromtimestamp(updated, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    else:
        date_published = ""

    return ModpackVersion(
        id=str(raw["id"]),
        version_number=raw["name"],
        name=raw["name"],
        loaders=loaders,
        game_versions=(mc_version,) if mc_version else (),
        date_published=date_published,
    )
