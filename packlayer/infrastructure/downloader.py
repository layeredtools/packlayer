from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import aiofiles

from packlayer.domain.exceptions import HashMismatch
from packlayer.domain.models import ModFile
from packlayer.interfaces.downloader import DownloadResult, FileDownloader
from packlayer.interfaces.http import HttpClient

logger = logging.getLogger("packlayer.downloader")

_CHUNK = 64 * 1024


class HttpDownloader(FileDownloader):
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def download(self, file: ModFile, dest: Path) -> DownloadResult:
        path = dest / file.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"downloading {file.filename} from {file.url}")

        bytes_written = await self._fetch(file.url, path)
        if file.hash is not None:
            logger.debug(f"verifying {file.filename} ({bytes_written} bytes)")
            self._verify(path, file.hash, file.hash_type)
        else:
            logger.debug(f"skipping hash verification for {file.filename}")
        return DownloadResult(file=file, path=path, bytes_written=bytes_written)

    async def _fetch(self, url: str, path: Path) -> int:
        written = 0
        async with aiofiles.open(path, "wb") as f:
            async for chunk in self._http.get_stream(url):
                await f.write(chunk)
                written += len(chunk)
        return written

    def _verify(self, path: Path, expected: str, hash_type: str | None) -> None:
        match hash_type:
            case "sha512":
                digest = hashlib.sha512()
            case "sha1":
                digest = hashlib.sha1()
            case _:
                return

        with path.open("rb") as f:
            while chunk := f.read(_CHUNK):
                digest.update(chunk)

        if digest.hexdigest() != expected:
            path.unlink(missing_ok=True)
            raise HashMismatch(path.name)
