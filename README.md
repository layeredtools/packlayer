<div align="center">

# packlayer

Async Python library for resolving and installing Minecraft modpacks.  
Embed it in your launcher, server panel, or automation scripts.

[![Python](https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/packlayer?style=flat-square)](https://pypi.org/project/packlayer/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./LICENSE)
[![Platform](https://img.shields.io/badge/platform-cross--platform-lightgrey?style=flat-square)]()

</div>

---

Supports Modrinth slugs, FTB pack IDs, direct `.mrpack` URLs, and local files. Handles concurrent downloads, hash verification, overrides, and client/server filtering. The resolver is pluggable — additional providers can be added without touching the library.

If you just want a CLI tool to install modpacks without writing any code, [mrpack-install](https://github.com/nothub/mrpack-install) is the right choice — it ships as a standalone binary with no runtime required. packlayer is for when you need modpack resolution and installation embedded in a Python project.

---

## Installation

```
pip install packlayer
```

**Requirements:** Python 3.12+

---

## Python API

### One-shot

```python
import asyncio
from packlayer import install_modpack

asyncio.run(install_modpack("mr:fabulously-optimized", "./instance"))
```

### Client

```python
import asyncio
from packlayer import PacklayerClient

async def main():
    async with PacklayerClient(minecraft_version="1.20.1") as client:
        versions = await client.list_versions("mr:fabulously-optimized")
        modpack  = await client.resolve("mr:fabulously-optimized", modpack_version=versions[0].version_number)
        result   = await client.install(modpack, "./instance")
        print(f"{result.total} files installed ({len(result.downloads)} mods, {result.override_count} overrides)")

asyncio.run(main())
```

### Progress tracking

```python
from packlayer import PacklayerClient

async def main():
    async with PacklayerClient() as client:
        modpack = await client.resolve("mr:fabulously-optimized")

        def on_start(total: int) -> None:
            print(f"downloading {total} files")

        def on_progress() -> None:
            print(".", end="", flush=True)

        await client.install(
            modpack, "./instance",
            on_start=on_start,
            on_progress=on_progress,
        )
```

`on_progress` is called once per installed file (mods and overrides). Both sync and async callables are accepted.

### Install options

```python
from packlayer import PacklayerClient, InstallOptions

async def main():
    async with PacklayerClient() as client:
        modpack = await client.resolve("ftb:79")
        await client.install(
            modpack, "./instance",
            options=InstallOptions(
                side="server",
                include_optional=False,
            ),
        )
```

### Plugin system

packlayer dispatches resolution to a registry of `ModpackResolver` instances. `extra_resolvers` are registered before built-ins, giving them higher priority.

```python
from packlayer.interfaces.resolver import ModpackResolver
from packlayer.domain.models import Modpack, ModpackVersion

class MyResolver(ModpackResolver):
    def can_handle(self, source: str) -> bool:
        return "myprovider.com" in source

    async def resolve(self, source: str, *, modpack_version: str | None = None) -> Modpack:
        ...

    async def fetch_versions(self, source: str) -> list[ModpackVersion]:
        ...

async with PacklayerClient(extra_resolvers=[MyResolver()]) as client:
    modpack = await client.resolve("https://myprovider.com/modpacks/mypack")
    await client.install(modpack, "./instance")
```

`can_handle` must be exclusive — return `True` only for sources this resolver definitively owns.

---

## Reference

### `install_modpack`

```python
async def install_modpack(
    source: str,
    dest: str | PathLike[str],
    *,
    minecraft_version: str | None = None,
    modpack_version: str | None = None,
    concurrency: int = 8,
    on_start: Callable[[int], None] | None = None,
    on_progress: ProgressCallback | None = None,
    options: InstallOptions | None = None,
    extra_resolvers: list[ModpackResolver] | None = None,
    default_resolver: ModpackResolver | None = None,
) -> InstallResult
```

| Parameter | Description |
|---|---|
| `source` | Local path, direct URL, `mr:<slug>`, Modrinth project URL, or `ftb:<id>` |
| `dest` | Destination directory. Created if it does not exist |
| `minecraft_version` | Filter versions by Minecraft version (e.g. `"1.20.1"`) |
| `modpack_version` | Pin a specific modpack version (e.g. `"6.0.1"`). Uses latest if omitted |
| `concurrency` | Max simultaneous downloads. Default: `8` |
| `on_start` | Callback invoked with the total file count before downloading starts |
| `on_progress` | Callback invoked after each installed file (sync or async, no arguments) |
| `options` | Controls which files are installed. See `InstallOptions` |
| `extra_resolvers` | Additional resolvers registered before built-ins |
| `default_resolver` | Fallback resolver when no registered resolver claims the source |

### `PacklayerClient`

```python
class PacklayerClient:
    def __init__(
        self,
        *,
        minecraft_version: str | None = None,
        concurrency: int = 8,
        extra_resolvers: list[ModpackResolver] | None = None,
        default_resolver: ModpackResolver | None = None,
        config: PacklayerConfig | None = None,
    ) -> None
```

Must be used as an async context manager.

| Method | Description |
|---|---|
| `resolve(source, *, modpack_version)` | Resolve a modpack without downloading files |
| `install(modpack, dest, *, on_start, on_progress, options)` | Install a resolved modpack to disk |
| `list_versions(source)` | Return available versions, newest-first |
| `resolver_for(source)` | Return the resolver that would handle `source` |
| `resolvers()` | Return all registered resolvers in priority order |

### Models

**`Modpack`**

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Display name |
| `version` | `str` | Version string |
| `minecraft_version` | `str` | Target Minecraft version |
| `files` | `tuple[ModFile, ...]` | Mod files to be downloaded |
| `overrides` | `tuple[Override, ...]` | Non-mod files to be written into the instance directory |

**`ModFile`**

| Field | Type | Description |
|---|---|---|
| `url` | `str` | Download URL |
| `filename` | `str` | Bare filename |
| `size` | `int` | Expected file size in bytes |
| `hash` | `str \| None` | Hex digest, verified post-download if provided |
| `hash_type` | `"sha512" \| "sha1" \| None` | Algorithm used for `hash` |
| `optional` | `bool` | Whether the file is optional |
| `side` | `"client" \| "server" \| "both"` | Which side this file targets |

**`Override`**

| Field | Type | Description |
|---|---|---|
| `path` | `str` | Destination path relative to the instance root (e.g. `"config/sodium.json"`) |
| `side` | `"client" \| "server" \| "both"` | Which side this override applies to |
| `data` | `bytes \| None` | Raw file contents bundled inline (e.g. from `.mrpack` zips). Mutually exclusive with `url` |
| `url` | `str \| None` | Remote URL to fetch the file from (e.g. FTB overrides). Mutually exclusive with `data` |

**`ModpackVersion`**

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Provider-assigned version ID |
| `version_number` | `str` | Human-readable version string |
| `name` | `str` | Release display name |
| `loaders` | `tuple[str, ...]` | Supported mod loaders |
| `game_versions` | `tuple[str, ...]` | Compatible Minecraft versions |
| `date_published` | `str` | ISO 8601 publish timestamp |

**`InstallOptions`**

| Field | Type | Default | Description |
|---|---|---|---|
| `include_optional` | `bool` | `True` | If `False`, optional files are skipped |
| `side` | `"client" \| "server" \| "both"` | `"client"` | Files incompatible with this side are skipped |

### Exceptions

All exceptions inherit from `PacklayerError`.

| Exception | Description |
|---|---|
| `LocalFileNotFound` | Local path does not exist |
| `InvalidMrpack` | File is not a valid `.mrpack` archive |
| `SlugNotFound` | No project matches the given slug or ID |
| `NoVersionFound` | Project exists but has no compatible version |
| `NoResolverFound` | No registered resolver claimed the source |
| `HashMismatch` | Hash digest mismatch after download |
| `NetworkError` | Network failure |

---

## Supported providers

| Provider | Source format | Auth required |
|---|---|---|
| Modrinth | `mr:<slug>`, Modrinth project URL, direct `.mrpack` URL, local `.mrpack` | No |
| FTB | `ftb:<id>`, `feed-the-beast.com` URL | No |

---

## CLI

A CLI is included for quick one-off installs. For production use, the Python API gives you full control.

```
packlayer install mr:fabulously-optimized
packlayer install ftb:79
packlayer install ./mypack.mrpack
packlayer install mr:fabulously-optimized --minecraft 1.20.1 --dest ./instance
```

| Flag | Description |
|---|---|
| `--dest <path>` | Output directory (default: `./dest`) |
| `--version <version>` | Pin a specific modpack version (e.g. `6.0.1`) |
| `--minecraft <version>` | Filter by Minecraft version (e.g. `1.20.1`) |
| `--side <client\|server\|both>` | Which side to install for (default: `client`) |
| `--no-optional` | Skip optional mods |
| `-v`, `--verbose` | Enable debug logging |