<div align="center">

# packlayer

Resolves and installs Minecraft modpacks from Modrinth slugs, FTB IDs, direct URLs, or local `.mrpack` files.  
One call. No launcher required.

[![Python](https://img.shields.io/badge/python-3.14%2B-blue?style=flat-square)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/packlayer?style=flat-square)](https://pypi.org/project/packlayer/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./LICENSE)
[![Platform](https://img.shields.io/badge/platform-cross--platform-lightgrey?style=flat-square)]()

<!-- replace with a demo gif once available -->

</div>

---

## What it does

You give it a modpack source — a Modrinth slug, an FTB pack ID, a direct `.mrpack` URL, or a local file — and it resolves the manifest, downloads all mod files concurrently, verifies their integrity, and drops them into a folder. There's a CLI for one-off use and a full async Python API for integration.

The resolver is provider-agnostic by design. Built-in support covers Modrinth and FTB. Additional providers can be plugged in without touching the library.

---

## Installation

```
pip install packlayer
```

**Requirements:** Python 3.14+

---

## Usage

### CLI

```
packlayer install mr:fabulously-optimized
```

```
packlayer install https://modrinth.com/modpack/fabulously-optimized
```

```
packlayer install ftb:79
```

```
packlayer install ./mypack.mrpack
```

```
packlayer install mr:fabulously-optimized --minecraft 1.20.1 --dest ./dest
```

### All options

| Flag | Description |
|---|---|
| `--dest <path>` | Output directory (default: `./mods`) |
| `--version <version>` | Pin a specific modpack version (e.g. `6.0.1`) |
| `--minecraft <version>` | Filter by Minecraft version (e.g. `1.20.1`) |
| `--side <client\|server\|both>` | Which side to install for (default: `client`) |
| `--no-optional` | Skip optional mods |
| `-v`, `--verbose` | Enable debug logging |

---

## Python API

### One-shot

```python
import asyncio
from packlayer import install_modpack

asyncio.run(install_modpack("mr:fabulously-optimized", "./mods"))
```

### Client

```python
import asyncio
from packlayer import PacklayerClient

async def main():
    async with PacklayerClient(minecraft_version="1.20.1") as client:
        versions = await client.list_versions("mr:fabulously-optimized")
        modpack  = await client.resolve("mr:fabulously-optimized", modpack_version=versions[0].version_number)
        results  = await client.install(modpack, "./mods")
        print(f"{len(results)} files installed")

asyncio.run(main())
```

### Progress tracking

```python
from packlayer import PacklayerClient, ModFile

async def main():
    async with PacklayerClient() as client:
        modpack = await client.resolve("mr:fabulously-optimized")

        def on_start(total: int) -> None:
            print(f"downloading {total} files")

        def on_file(file: ModFile) -> None:
            print(f"  {file.filename}")

        await client.install(
            modpack, "./mods",
            on_start=on_start,
            on_progress=on_file,
        )
```

### Install options

```python
from packlayer import PacklayerClient, InstallOptions

async def main():
    async with PacklayerClient() as client:
        modpack = await client.resolve("ftb:79")
        await client.install(
            modpack, "./mods",
            options=InstallOptions(
                side="server",
                include_optional=False,
            ),
        )
```

---

## Reference

### `install_modpack`

```python
async def install_modpack(
    source: str,
    dest: str | PathLike[str],
    *,
    minecraft_version: str | None = None,
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
| `concurrency` | Max simultaneous downloads. Default: `8` |
| `on_start` | Callback invoked with the total file count before downloading starts |
| `on_progress` | Callback invoked after each downloaded file (sync or async) |
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
    ) -> None
```

Must be used as an async context manager.

| Method | Description |
|---|---|
| `resolve(source, *, modpack_version)` | Resolve a modpack without downloading files |
| `install(source, dest, *, on_start, on_progress, options)` | Resolve and install a modpack |
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
| `files` | `tuple[ModFile, ...]` | Files to be downloaded |

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
| `HashMismatch` | Hash digest mismatch after download |
| `NetworkError` | Network failure |
| `NoResolverFound` | No registered resolver claimed the source |

---

## Supported providers

| Provider | Source format | Auth required |
|---|---|---|
| Modrinth | `mr:<slug>`, Modrinth project URL, direct `.mrpack` URL, local `.mrpack` | No |
| FTB | `ftb:<id>`, `feed-the-beast.com` URL | No |

---

## Plugin system

packlayer dispatches resolution to a registry of `ModpackResolver` instances. `extra_resolvers` are registered before built-ins, giving them higher priority.

### Implementing a resolver

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
```

`can_handle` must be exclusive — return `True` only for sources this resolver definitively owns.

### Registering

```python
async with PacklayerClient(extra_resolvers=[MyResolver()]) as client:
    modpack = await client.resolve("https://myprovider.com/modpacks/mypack")
    await client.install(modpack, "./mods")
```

---
