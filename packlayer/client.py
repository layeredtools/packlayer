from __future__ import annotations

import os
from typing import Callable
from pathlib import Path

from inspect import iscoroutinefunction
import asyncio

from packlayer.domain.models import Modpack, ModpackVersion
from packlayer.infrastructure.http import PacklayerHTTP
from packlayer.infrastructure.downloader import HttpDownloader
from packlayer.infrastructure.installer import InstallModpack, InstallResult
from packlayer.interfaces.resolver import ModpackResolver
from packlayer.providers import ModrinthResolver, FTBResolver
from packlayer.providers.registry import ResolverRegistry
from packlayer.domain.models import InstallOptions
from packlayer.domain.config import PacklayerConfig
from packlayer.types import MinecraftVersion, ProgressCallback


def wrap_progress(cb: ProgressCallback) -> Callable[[], None]:
    """
    Normalise a progress callback so the installer always receives a plain
    sync callable, regardless of whether the caller supplied an async one.

    Async callbacks are scheduled as fire-and-forget tasks on the running
    event loop so they don't block the download pipeline.
    """
    if iscoroutinefunction(cb):

        def wrapper() -> None:
            asyncio.get_running_loop().create_task(cb())

        return wrapper
    return cb  # type: ignore[return-value]


class PacklayerClient:
    """
    High-level async client for interacting with packlayer.

    Must be used as an async context manager to ensure the underlying HTTP
    session is properly opened and closed.

    Parameters
    ----------
    minecraft_version:
        Optional Minecraft version filter.
    concurrency:
        Maximum simultaneous file downloads. Defaults to 8.
    extra_resolvers:
        Additional resolvers registered before the built-ins, giving them
        higher priority. Useful for third-party providers or overriding
        built-in resolution behaviour. Each resolver must implement
        :class:`~packlayer.interfaces.resolver.ModpackResolver` and return
        ``True`` from ``can_handle`` only for sources it owns.
    default_resolver:
        Fallback resolver used when no registered resolver claims the source.
        If omitted and no resolver matches, :exc:`~packlayer.NoResolverFound`
        is raised.
    config:
        Optional :class:`~packlayer.domain.config.PacklayerConfig` instance.
        Values from the config are used as defaults; explicit constructor
        arguments take precedence.

    Example
    -------
    ```python
        async with PacklayerClient(minecraft_version="1.20.1") as client:
            versions = await client.list_versions("mr:fabulously-optimized")
            modpack  = await client.resolve("mr:fabulously-optimized", modpack_version=versions[0].version_number)
            result   = await client.install(modpack, "./instance")
            print(f"{result.total} files installed ({len(result.downloads)} mods, {result.override_count} overrides)")
    ```

    Plugin example
    --------------
    ```python
        async with PacklayerClient(extra_resolvers=[MyCurseForgeResolver()]) as client:
            modpack = await client.resolve("https://curseforge.com/minecraft/modpacks/...")
            await client.install(modpack, "./instance")
    ```
    """

    def __init__(
        self,
        *,
        minecraft_version: MinecraftVersion | None = None,
        concurrency: int = 8,
        extra_resolvers: list[ModpackResolver] | None = None,
        default_resolver: ModpackResolver | None = None,
        config: PacklayerConfig | None = None,
    ) -> None:
        self._config = cfg = config or PacklayerConfig()
        self._minecraft_version = minecraft_version or cfg.minecraft_version
        self._concurrency = concurrency or cfg.concurrency
        self._extra_resolvers = extra_resolvers or []
        self._default_resolver = default_resolver

        self._http: PacklayerHTTP | None = None
        self._registry: ResolverRegistry | None = None

    async def __aenter__(self) -> PacklayerClient:
        self._http = PacklayerHTTP(retry=self._config.retry)
        await self._http.__aenter__()

        self._registry = ResolverRegistry()
        if self._default_resolver:
            self._registry.set_default_resolver(self._default_resolver)

        for r in self._extra_resolvers:
            self._registry.register(r)

        self._registry.register(FTBResolver(self._http, self._minecraft_version))
        self._registry.register(ModrinthResolver(self._http, self._minecraft_version))
        return self

    async def __aexit__(self, *_) -> None:
        if self._http:
            await self._http.__aexit__(None, None, None)
            self._http = None

    def resolvers(self) -> list[ModpackResolver]:
        """Return all registered resolvers in priority order."""
        return self._require_registry().resolvers()

    async def list_versions(self, source: str) -> list[ModpackVersion]:
        """
        Return all available versions of a modpack, newest-first.

        Dispatches to the appropriate registered resolver via
        :class:`~packlayer.providers.registry.ResolverRegistry`.
        Optionally filtered by the ``minecraft_version`` passed at
        construction time, if the resolver supports it.

        Parameters
        ----------
        source:
            A source string accepted by any registered resolver
            (e.g. ``"fabulously-optimized"``, ``"https://modrinth.com/modpack/..."``).

        Returns
        -------
        list[ModpackVersion]

        Raises
        ------
        NoResolverFound
            No registered resolver claimed the source.
        PacklayerError
            The resolver failed to fetch versions (slug not found, network error, etc.).
        """
        return await self._require_registry().pick(source).fetch_versions(source)

    async def resolve(
        self, source: str, *, modpack_version: str | None = None
    ) -> Modpack:
        """
        Resolve a modpack from ``source`` without downloading its files.

        Dispatches to the appropriate registered resolver via
        :class:`~packlayer.providers.registry.ResolverRegistry`. Returns a
        :class:`~packlayer.Modpack` containing metadata and the full file list,
        ready to be passed to :meth:`install`.

        Raises
        ------
        NoResolverFound
            No registered resolver claimed the source.
        PacklayerError
            Resolution failed (invalid file, slug not found, network error, etc.).
        """
        return await self.resolver_for(source).resolve(
            source, modpack_version=modpack_version
        )

    async def install(
        self,
        modpack: Modpack,
        dest: str | os.PathLike[str],
        *,
        on_start: Callable[[int], None] | None = None,
        on_progress: ProgressCallback | None = None,
        options: InstallOptions | None = None,
    ) -> InstallResult:
        """
        Install a modpack to ``dest``.

        Mods are placed in ``dest/mods/``. Override files (configs, scripts,
        resource packs, etc.) are written relative to ``dest/``, preserving
        the directory structure declared by the modpack.

        Parameters
        ----------
        modpack:
            A resolved :class:`~packlayer.Modpack` from :meth:`resolve`.
        dest:
            Instance root directory. Created if it does not exist. Mods go
            into ``dest/mods/``; overrides are written relative to ``dest/``.
        on_start:
            Optional callback invoked with the total file count (mods +
            overrides) before downloading starts.
        on_progress:
            Optional callback invoked after each file is installed (both mods
            and overrides). Sync and async callables are both accepted.
        options:
            Controls which files are downloaded. See :class:`~packlayer.InstallOptions`.

        Returns
        -------
        InstallResult

        Raises
        ------
        PacklayerError
            If download or hash verification fails.
        ValueError
            If ``dest`` exists but is not a directory.
        """
        dest = Path(dest).expanduser().resolve()
        if dest.exists() and not dest.is_dir():
            raise ValueError(f"destination must be a directory: {dest}")

        installer = InstallModpack(
            downloader=HttpDownloader(self._require_http()),
            on_start=on_start,
            on_progress=wrap_progress(on_progress) if on_progress else None,
            concurrency=self._concurrency,
            options=options,
        )
        return await installer.install(modpack, dest)

    def resolver_for(self, source: str) -> ModpackResolver:
        """Return the resolver that would handle ``source``."""
        return self._require_registry().pick(source)

    def _require_http(self) -> PacklayerHTTP:
        if self._http is None:
            raise RuntimeError(
                "PacklayerClient must be used as an async context manager:\n"
                "\n"
                "    async with PacklayerClient() as client:\n"
                "        ...\n"
            )
        return self._http

    def _require_registry(self) -> ResolverRegistry:
        if self._registry is None:
            raise RuntimeError(
                "PacklayerClient must be used as an async context manager:\n"
                "\n"
                "    async with PacklayerClient() as client:\n"
                "        ...\n"
            )
        return self._registry


async def install_modpack(
    source: str,
    dest: str | os.PathLike[str],
    *,
    minecraft_version: str | None = None,
    modpack_version: str | None = None,
    concurrency: int = 8,
    on_start: Callable[[int], None] | None = None,
    on_progress: ProgressCallback | None = None,
    options: InstallOptions | None = None,
    extra_resolvers: list[ModpackResolver] | None = None,
    default_resolver: ModpackResolver | None = None,
) -> InstallResult:
    """
    Install a Minecraft modpack in a single call.

    Convenience wrapper around :class:`PacklayerClient`. For multiple
    operations, fine-grained control, or custom resolvers, use the client
    directly.

    Parameters
    ----------
    source:
        Any source string accepted by a registered resolver — local path,
        direct URL, or provider-prefixed ID (e.g. ``"mr:fabulously-optimized"``,
        ``"ftb:79"``).
    dest:
        Instance root directory. Mods go into ``dest/mods/``; overrides are
        written relative to ``dest/``.
    minecraft_version:
        Optional Minecraft version filter, passed through to resolvers
        that support it.
    modpack_version:
        Pin a specific modpack version (e.g. ``"6.0.1"``). If omitted,
        the latest compatible version is used.
    concurrency:
        Maximum simultaneous downloads. Defaults to 8.
    on_start:
        Optional callback invoked with the total file count (mods + overrides)
        before downloading starts.
    on_progress:
        Optional callback (sync or async) invoked after each installed file
        (both mods and overrides).
    options:
        Controls which files are downloaded. See :class:`~packlayer.InstallOptions`.
    extra_resolvers:
        Additional resolvers registered before the built-ins.
    default_resolver:
        Fallback resolver when no registered resolver claims the source.

    Returns
    -------
    InstallResult

    Raises
    ------
    NoResolverFound
        No registered resolver claimed the source.
    PacklayerError
        If resolution, download, or verification fails.

    Examples
    --------
    Basic::

        asyncio.run(install_modpack("mr:fabulously-optimized", "./instance"))

    With async progress::

        async def on_file():
            await ws.send("progress")

        asyncio.run(
            install_modpack("mr:pack.mrpack", "./instance", on_progress=on_file)
        )
    """
    async with PacklayerClient(
        minecraft_version=minecraft_version,
        concurrency=concurrency,
        extra_resolvers=extra_resolvers,
        default_resolver=default_resolver,
    ) as client:
        modpack = await client.resolve(source, modpack_version=modpack_version)
        return await client.install(
            modpack,
            dest,
            on_start=on_start,
            on_progress=on_progress,
            options=options,
        )
