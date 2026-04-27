# Packlayer

Packlayer is a high-level asynchronous Python library for resolving and installing Minecraft modpacks from multiple sources — local `.mrpack` files, direct URLs, Modrinth slugs, and FTB pack IDs.

It is designed to be simple to use while remaining flexible and extensible, making it suitable for both one-off scripts and integration into larger applications such as launchers, server panels, and deployment pipelines.

If you just want a CLI tool to install modpacks without writing any code, [mrpack-install](https://github.com/nothub/mrpack-install) ships as a standalone binary with no runtime required. Packlayer is for when you need modpack resolution and installation embedded in a Python project.

---

## Installation

```bash
pip install packlayer
```

**Requirements:** Python 3.12+

---

## Quick Start

```python
import asyncio
from packlayer import PacklayerClient

async def main():
    async with PacklayerClient(minecraft_version="1.20.1") as client:
        versions = await client.list_versions("mr:fabulously-optimized")
        modpack = await client.resolve(
            "mr:fabulously-optimized",
            modpack_version=versions[0].version_number,
        )
        result = await client.install(modpack, "./instance")

        print(f"{result.total} files installed")
        print(f"{len(result.downloads)} mods downloaded")
        print(f"{result.override_count} overrides applied")

asyncio.run(main())
```

For simple one-off installs, the `install_modpack` convenience function skips the boilerplate:

```python
import asyncio
from packlayer import install_modpack

asyncio.run(install_modpack("mr:fabulously-optimized", "./instance"))
```

---

## Core Concepts

### Modpack Resolution

Resolution is the process of turning a source string into a `Modpack` object — a parsed description of all the files that need to be installed. Packlayer supports:

- **Local files** — any path ending in `.mrpack` or pointing to an existing file
- **Direct URLs** — any HTTP(S) URL ending in `.mrpack`
- **Modrinth** — `mr:<slug>`, full Modrinth project URLs
- **FTB** — `ftb:<id>`, `feed-the-beast.com` URLs

Resolution does not download mod files. It only fetches and parses the modpack manifest. Download happens separately during installation, giving you the opportunity to inspect or filter the file list first.

---

### Versions

There are two distinct version concepts in Packlayer:

- **Modpack version** — a specific release of a modpack (e.g. `"0.7.3"`). Returned by `list_versions`, passed to `resolve` to pin a release.
- **Minecraft version** — a compatibility filter (e.g. `"1.20.1"`). Passed to the client constructor and used to narrow version listings.

List available versions:

```python
versions = await client.list_versions("mr:fabulously-optimized")
for v in versions:
    print(v.version_number, v.game_versions, v.date_published)
```

Resolve the latest version:

```python
modpack = await client.resolve("mr:fabulously-optimized")
```

Resolve a specific version:

```python
modpack = await client.resolve(
    "mr:fabulously-optimized",
    modpack_version="0.7.3",
)
```

---

### Installation

Once resolved, a `Modpack` can be installed to a local directory:

```python
result = await client.install(modpack, "./instance")
```

Mods are placed in `./instance/mods/`. Override files — configs, scripts, resource packs, and anything else bundled by the modpack — are written relative to `./instance/`, preserving their declared directory structure.

The installation process:

- Downloads all required mod files concurrently
- Verifies sha512/sha1 hashes post-download, raising `HashMismatch` on failure
- Skips files incompatible with the configured side or marked optional when `include_optional=False`
- Writes override files, fetching them remotely if needed (e.g. FTB overrides)

---

### Progress Tracking

Both `on_start` and `on_progress` callbacks are available to track installation progress. Sync and async callables are both accepted.

```python
def on_start(total: int) -> None:
    print(f"installing {total} files...")

def on_progress() -> None:
    print(".", end="", flush=True)

result = await client.install(
    modpack, "./instance",
    on_start=on_start,
    on_progress=on_progress,
)
```

`on_start` is called once before downloading begins with the total file count (mods + overrides). `on_progress` is called once per installed file.

---

### Install Options

Installation behaviour can be customised using `InstallOptions`:

```python
from packlayer import InstallOptions

options = InstallOptions(
    side="server",           # "client" | "server" | "both"  (default: "client")
    include_optional=False,  # skip optional mods             (default: True)
)

result = await client.install(modpack, "./instance", options=options)
```

Files whose `side` is incompatible with the chosen option are silently skipped. This is useful for building server deployments from a client-side modpack without manually filtering the file list.

---

### Install Results

`install` returns an `InstallResult`:

```python
result = await client.install(modpack, "./instance")

print(result.total)           # total files installed (mods + overrides)
print(result.override_count)  # number of override files written
for download in result.downloads:
    print(download.file.filename, download.bytes_written)
```

Each `DownloadResult` in `result.downloads` includes the associated `ModFile` metadata, the destination `Path`, and the number of bytes written. These are useful for logging, reporting, and post-install validation.

---

## Extensibility

Packlayer resolves sources through a registry of `ModpackResolver` instances. Built-in resolvers cover Modrinth and FTB. You can add support for additional providers by implementing the `ModpackResolver` interface and registering it via `extra_resolvers`.

```python
from packlayer.interfaces.resolver import ModpackResolver
from packlayer.domain.models import Modpack, ModpackVersion

class MyResolver(ModpackResolver):
    def can_handle(self, source: str) -> bool:
        # return True only for sources this resolver definitively owns
        return source.startswith("myprovider:")

    async def resolve(
        self, source: str, *, modpack_version: str | None = None
    ) -> Modpack:
        # fetch and return a parsed Modpack
        ...

    async def fetch_versions(self, source: str) -> list[ModpackVersion]:
        # return available versions, newest-first
        ...
```

Register it when constructing the client:

```python
async with PacklayerClient(extra_resolvers=[MyResolver()]) as client:
    modpack = await client.resolve("myprovider:some-pack")
    await client.install(modpack, "./instance")
```

`extra_resolvers` are registered before the built-ins, giving them higher priority. If no resolver claims a source, `NoResolverFound` is raised. A `default_resolver` can be provided as a catch-all fallback.

---

## Configuration

Packlayer can be configured via TOML files, which define default behaviour for the client — useful mainly for CLI usage. When using the Python API directly, constructor arguments are the preferred way to configure the client; they always take precedence over any loaded config.

When no explicit config path is provided, Packlayer searches these locations in order:

1. `.packlayer.toml` (current working directory)
2. `packlayer.toml` (current working directory)
3. `~/.config/packlayer/config.toml`

The first file found is loaded. If none are present, defaults are used.

### Example

```toml
concurrency = 8
minecraft_version = "1.20.1"

[install]
dest = "./dest"
side = "client"
include_optional = true

[retry]
max_retries = 5
backoff_base = 2.0
retryable_statuses = [429, 500, 502, 503, 504]
```

### Reference

**Top-level**

| Key | Type | Default | Description |
|---|---|---|---|
| `concurrency` | `int` | `8` | Maximum simultaneous downloads |
| `minecraft_version` | `str` | `null` | Default Minecraft version filter |

**`[install]`**

| Key | Type | Default | Description |
|---|---|---|---|
| `dest` | `str` | `"./dest"` | Default installation directory |
| `side` | `str` | `"client"` | Target side: `"client"`, `"server"`, or `"both"` |
| `include_optional` | `bool` | `true` | Whether to include optional mod files |

**`[retry]`**

| Key | Type | Default | Description |
|---|---|---|---|
| `max_retries` | `int` | `5` | Maximum retry attempts for failed requests |
| `backoff_base` | `float` | `2.0` | Exponential backoff base (seconds) |
| `retryable_statuses` | `int[]` | `[429, 500, 502, 503, 504]` | HTTP status codes that trigger a retry |

---

## Error Handling

All exceptions inherit from `PacklayerError` and are importable directly from `packlayer`:

```python
from packlayer import (
    PacklayerError,
    NoResolverFound,
    SlugNotFound,
    NoVersionFound,
    InvalidMrpack,
    LocalFileNotFound,
    HashMismatch,
    NetworkError,
)
```

| Exception | When it's raised |
|---|---|
| `NoResolverFound` | No registered resolver claimed the source string |
| `SlugNotFound` | The slug or ID does not exist on the provider |
| `NoVersionFound` | The modpack exists but has no compatible version |
| `InvalidMrpack` | The `.mrpack` file is missing required fields or malformed |
| `LocalFileNotFound` | The local path does not exist |
| `HashMismatch` | Downloaded file failed hash verification |
| `NetworkError` | A network failure occurred (connection error, repeated 5xx, etc.) |

A typical error handling pattern:

```python
from packlayer import PacklayerClient, NoVersionFound, NetworkError

async with PacklayerClient(minecraft_version="1.20.1") as client:
    try:
        modpack = await client.resolve("mr:fabulously-optimized")
        await client.install(modpack, "./instance")
    except NoVersionFound as e:
        print(f"no compatible version: {e}")
    except NetworkError as e:
        print(f"network failure: {e}")
```