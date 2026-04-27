from __future__ import annotations
import logging
from pathlib import Path
import aiofiles
from packlayer.domain.exceptions import (
    InvalidMrpack,
    LocalFileNotFound,
    NoVersionFound,
    SlugNotFound,
    NetworkError,
)
from packlayer.domain.models import Modpack, ModpackVersion
from packlayer.interfaces.http import HttpClient
from packlayer.interfaces.resolver import ModpackResolver
from packlayer.providers.modrinth.parser import extract_index, parse_modpack
from packlayer.providers.modrinth.slug import (
    extract_slug,
    is_local,
    is_direct_url,
    is_modrinth_id,
)
from packlayer.types import MinecraftVersion

logger = logging.getLogger("packlayer.modrinth")

_API = "https://api.modrinth.com/v2"


class ModrinthResolver(ModpackResolver):
    """
    Resolves Modrinth modpacks from multiple source types: local `.mrpack` files,
    direct download URLs, or Modrinth project slugs/URLs.

    Implements :class:`ModpackResolver` using the Modrinth v2 API and an
    injected :class:`HttpClient` for all network I/O.

    Args:
        http: Async HTTP client used for API calls and file downloads.
        minecraft_version: If provided, filters version listings to only
            include releases compatible with this Minecraft version
            (e.g. ``"1.20.1"``). Has no effect on local/URL resolution.
    """

    def __init__(
        self,
        http: HttpClient,
        minecraft_version: MinecraftVersion | None = None,
    ) -> None:
        self._http = http
        self._minecraft_version = minecraft_version

    def can_handle(self, source: str) -> bool:
        return (
            is_local(source)
            or is_direct_url(source)
            or "modrinth.com" in source
            or is_modrinth_id(source)
        )

    async def resolve(
        self, source: str, *, modpack_version: str | None = None
    ) -> Modpack:
        """
        Resolve a modpack from ``source``, auto-detecting its type.

        Resolution order:
        1. **Local path** — if ``source`` looks like a file path, reads it from disk.
        2. **Direct URL** — if ``source`` is an HTTP(S) URL, downloads it directly.
        3. **Slug / project URL** — otherwise treats ``source`` as a Modrinth slug
            or project page URL and fetches the latest compatible version via the API.

        Args:
            source: A local file path, direct `.mrpack` URL, or Modrinth slug/URL.
            version: The modpack version you want to resolve to when using a slug.

        Returns:
            A parsed :class:`Modpack` instance.

        Raises:
            LocalFileNotFound: The local path does not exist.
            InvalidMrpack: The file is not a valid `.mrpack` archive.
            SlugNotFound: No Modrinth project matches the given slug.
            NoVersionFound: The project exists but has no compatible version.
            NetworkError: A non-404 network failure occurred.
        """
        if is_local(source):
            return await self._resolve_local(source)

        if is_direct_url(source):
            return await self._resolve_url(source)
        return await self._resolve_slug(source, modpack_version=modpack_version)

    async def fetch_versions(self, slug: str) -> list[ModpackVersion]:
        """
        Fetch all available modpack versions for a Modrinth project.

        Applies the same loader and Minecraft version filters as [`resolve`][resolve].
        Only versions that include a `.mrpack` file are returned.

        Args:
            slug: A Modrinth project slug or full project URL.

        Returns:
            A list of [`ModpackVersion`][ModpackVersion] objects, ordered by the API
            (newest first).

        Raises:
            SlugNotFound: No project matches the given slug.
            NoVersionFound: The project exists but has no compatible versions.
            NetworkError: A non-404 network failure occurred.
        """
        raw = await self._fetch_raw_versions(extract_slug(slug))
        return [_parse_version(v) for v in raw]

    async def _resolve_local(self, source: str) -> Modpack:
        path = Path(source)
        if not path.exists():
            raise LocalFileNotFound(source)
        raw = await self._read_bytes(path)

        try:
            index, zf = extract_index(raw)
        except Exception as e:
            raise InvalidMrpack(str(e)) from e

        return parse_modpack(index, zf)

    async def _read_bytes(self, path: Path) -> bytes:
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def _resolve_url(self, source: str) -> Modpack:
        raw = await self._http.get_bytes(source)
        try:
            index, zf = extract_index(raw)
        except Exception as e:
            raise InvalidMrpack(str(e)) from e
        return parse_modpack(index, zf)

    async def _resolve_slug(
        self, source: str, modpack_version: str | None = None
    ) -> Modpack:
        slug = extract_slug(source)
        logger.debug(f"resolved slug: {slug!r}")

        raw_versions = await self._fetch_raw_versions(slug)
        if modpack_version:
            selected = next(
                (v for v in raw_versions if v["version_number"] == modpack_version),
                None,
            )
            if not selected:
                raise NoVersionFound(slug, self._minecraft_version)

            chosen = selected
        else:
            chosen = raw_versions[0]  # latest

        logger.debug(f"selected version: {chosen['version_number']}")

        raw = await self._download_mrpack(chosen)
        index, zf = extract_index(raw)
        return parse_modpack(index, zf)

    async def _fetch_raw_versions(self, slug: str) -> list[dict]:
        params: dict = {"loaders": '["fabric","quilt","forge","neoforge"]'}
        if self._minecraft_version:
            params["game_versions"] = f'["{self._minecraft_version}"]'

        try:
            all_versions = await self._http.get_json(
                f"{_API}/project/{slug}/version",
                params=params,
            )
        except NetworkError as e:
            if "404" in str(e):
                raise SlugNotFound(slug) from e
            raise

        mrpack_versions = [
            v
            for v in all_versions
            if any(f["filename"].endswith(".mrpack") for f in v.get("files", []))
        ]
        if not mrpack_versions:
            raise NoVersionFound(slug, self._minecraft_version)

        return mrpack_versions

    async def _download_mrpack(self, raw_version: dict) -> bytes:
        mrpack = next(
            f for f in raw_version["files"] if f["filename"].endswith(".mrpack")
        )
        logger.debug(f"downloading mrpack: {mrpack['filename']}")

        return await self._http.get_bytes(mrpack["url"])


def _parse_version(raw: dict) -> ModpackVersion:
    return ModpackVersion(
        id=raw["id"],
        version_number=raw["version_number"],
        name=raw["name"],
        loaders=tuple(raw.get("loaders", [])),
        game_versions=tuple(raw.get("game_versions", [])),
        date_published=raw["date_published"],
    )
