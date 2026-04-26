from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from packlayer.domain import ModFile


@dataclass(frozen=True)
class DownloadResult:
    file: ModFile
    path: Path
    bytes_written: int


class FileDownloader(ABC):
    @abstractmethod
    async def download(self, file: ModFile, dest: Path) -> DownloadResult: ...
