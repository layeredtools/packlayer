from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from packlayer.domain.models import ModFile, Modpack, InstallOptions, Override
from packlayer.domain.exceptions import NetworkError
from packlayer.interfaces.downloader import DownloadResult, FileDownloader

_DEFAULT_CONCURRENCY = 8


@dataclass
class InstallResult:
    """Result of a completed modpack installation.

    Attributes
    ----------
    downloads:
        List of completed mod file downloads.
    override_count:
        Number of override files written (configs, scripts, etc.).
    """

    downloads: list[DownloadResult]
    override_count: int

    @property
    def total(self) -> int:
        """Total number of files installed (mods + overrides)."""
        return len(self.downloads) + self.override_count


class InstallModpack:
    def __init__(
        self,
        downloader: FileDownloader,
        on_start: Callable[[int], None] | None = None,
        on_progress: Callable[[], None] | None = None,
        concurrency: int = _DEFAULT_CONCURRENCY,
        options: InstallOptions | None = None,
    ) -> None:
        self._downloader = downloader
        self._on_start = on_start
        self._on_progress = on_progress
        self._concurrency = concurrency
        self._options = options or InstallOptions()

    async def install(self, modpack: Modpack, dest: Path) -> InstallResult:
        mods_dir = dest / "mods"
        opts = self._options

        files = [
            f
            for f in modpack.files
            if (opts.include_optional or not f.optional)
            and (f.side == "both" or f.side == opts.side or opts.side == "both")
        ]
        applicable_overrides = [
            o
            for o in modpack.overrides
            if o.side == "both" or o.side == opts.side or opts.side == "both"
        ]

        if self._on_start:
            self._on_start(len(files) + len(applicable_overrides))

        sem = asyncio.Semaphore(self._concurrency)
        tasks = [self._download_one(f, mods_dir, sem) for f in files]
        raw = await asyncio.gather(*tasks, return_exceptions=True)

        errors = [r for r in raw if isinstance(r, BaseException)]
        if errors:
            raise errors[0]

        override_count = await self._write_overrides(applicable_overrides, dest)
        downloads = [r for r in raw if isinstance(r, DownloadResult)]

        return InstallResult(downloads=downloads, override_count=override_count)

    async def _write_overrides(self, overrides: list[Override], dest: Path) -> int:
        count = 0
        for override in overrides:
            out = dest / override.path
            out.parent.mkdir(parents=True, exist_ok=True)
            if override.data is not None:
                out.write_bytes(override.data)
            elif override.url is not None:
                override_file = ModFile(url=override.url, filename=out.name, size=0)
                try:
                    await self._downloader.download(override_file, out.parent)
                except NetworkError as e:
                    raise NetworkError(f"{override.path}: {override.url} — {e}") from e
            count += 1
            if self._on_progress:
                self._on_progress()
        return count

    async def _download_one(
        self, file: ModFile, dest: Path, sem: asyncio.Semaphore
    ) -> DownloadResult:
        async with sem:
            result = await self._downloader.download(file, dest)
            if self._on_progress:
                self._on_progress()
            return result
