from __future__ import annotations


class PacklayerError(Exception):
    """Base exception for all packlayer errors."""


class ResolveError(PacklayerError):
    """Failed to resolve a modpack."""


class LocalFileNotFound(ResolveError):
    def __init__(self, path: str) -> None:
        super().__init__(f"file not found: {path}")


class InvalidMrpack(ResolveError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"invalid .mrpack: {reason}")


class SlugNotFound(ResolveError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"modpack not found on Modrinth: {slug!r}")


class NoVersionFound(ResolveError):
    def __init__(self, slug: str, minecraft_version: str | None) -> None:
        mc = f" for Minecraft {minecraft_version}" if minecraft_version else ""
        super().__init__(f"no .mrpack version found for {slug!r}{mc}")


class NoResolverFound(ResolveError):
    def __init__(self, source: str) -> None:
        super().__init__(f"no resolver can handle source: {source!r}")


class DownloadError(PacklayerError):
    """Failed to download a file."""


class HashMismatch(DownloadError):
    def __init__(self, filename: str) -> None:
        super().__init__(f"sha512 mismatch — file may be corrupted: {filename}")


class NetworkError(PacklayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"network error: {reason}")
