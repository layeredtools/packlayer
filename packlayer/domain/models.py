from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ModFile:
    """A single file entry within a modpack.

    Attributes
    ----------
    url:
        Remote download URL for the file.
    filename:
        Bare filename (no directory component) used when writing to disk.
    size:
        Expected file size in bytes, as declared in the modpack index.
    hash:
        Optional expected hex digest. Verified after download; raises
        :exc:`~packlayer.HashMismatch` if the digest does not match.
    hash_type:
        The type of said hash, e.g: ``"sha512"``, ``"sha1"``, etc.
    optional:
        Whether this mod is optional.
    side:
        Whether the mod is client-side, server-side, or both.
    """

    url: str
    filename: str
    size: int
    hash: str | None = None
    hash_type: Literal["sha512", "sha1"] | None = None
    optional: bool = False
    side: Literal["client", "server", "both"] = "both"


@dataclass(frozen=True)
class Override:
    """A non-mod file to be written into the instance directory after installation.

    Overrides cover anything outside ``mods/`` — configs, scripts, resource packs,
    shader settings, etc. The content is either bundled inline (``data``) or fetched
    from a remote URL (``url``); exactly one should be set.

    Attributes
    ----------
    path:
        Destination path relative to the instance root (e.g. ``"config/sodium.json"``).
        Parent directories are created automatically during installation.
    side:
        Which side this override applies to. Overrides incompatible with the
        chosen :class:`InstallOptions` side are skipped during installation.
    data:
        Raw file contents to write directly to disk. Set by resolvers that
        bundle overrides inside the package itself (e.g. ``.mrpack`` zips).
        Mutually exclusive with ``url``.
    url:
        Remote URL to fetch the file from. Set by resolvers where override
        files are hosted separately (e.g. FTB). Mutually exclusive with ``data``.
    """

    path: str
    side: Literal["client", "server", "both"] = "both"
    data: bytes | None = None
    url: str | None = None


@dataclass(frozen=True)
class Modpack:
    """A resolved modpack ready for installation.

    Attributes
    ----------
    name:
        Human-readable display name of the modpack.
    version:
        Version identifier string (e.g. ``"1.8.3"``).
    minecraft_version:
        The Minecraft version this modpack targets (e.g. ``"1.20.1"``).
    files:
        Immutable sequence of :class:`ModFile` entries to be downloaded.
        Empty by default for modpacks that declare no files.
    overrides:
        Immutable sequence of :class:`Override` entries to be written to the
        instance directory. Empty by default.
    """

    name: str
    version: str
    minecraft_version: str
    files: tuple[ModFile, ...] = field(default_factory=tuple)
    overrides: tuple[Override, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ModpackVersion:
    """Metadata for a single releasable version of a modpack.

    Returned by :meth:`~packlayer.PacklayerClient.list_versions`. Use
    ``version_number`` to pin a specific release when calling
    :meth:`~packlayer.PacklayerClient.resolve`.

    Attributes
    ----------
    id:
        Opaque provider-assigned identifier for this version.
    version_number:
        Human-readable version string (e.g. ``"5.4.0-beta.3"``).
    name:
        Display name of the release (may differ from ``version_number``).
    loaders:
        Mod loaders this version supports (e.g. ``("fabric", "quilt")``).
    game_versions:
        Minecraft versions this release is compatible with
        (e.g. ``("1.20.1",)``).
    date_published:
        ISO 8601 timestamp of when this version was published
        (e.g. ``"2024-03-15T10:00:00Z"``).
    """

    id: str
    version_number: str
    name: str
    loaders: tuple[str, ...]
    game_versions: tuple[str, ...]
    date_published: str


@dataclass(frozen=True)
class InstallOptions:
    """Controls which files are downloaded during installation.

    Attributes
    ----------
    include_optional:
        If ``False``, files marked optional by the modpack are skipped.
        Defaults to ``True``.
    side:
        Which side to install for. Files incompatible with the chosen side
        are skipped. Defaults to ``"client"``.
    """

    include_optional: bool = True
    side: Literal["client", "server", "both"] = "client"
