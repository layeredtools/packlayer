from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from packlayer.domain import ModFile


@dataclass(frozen=True)
class DownloadResult:
    """Represents the outcome of a single file download.

    Attributes
    ----------
    file:
        The :class:`ModFile` associated with this download.
    path:
        Filesystem path where the file was written.
    bytes_written:
        Total number of bytes written to disk.
    """

    file: ModFile
    path: Path
    bytes_written: int


class FileDownloader(ABC):
    @abstractmethod
    async def download(self, file: ModFile, dest: Path) -> DownloadResult: ...
