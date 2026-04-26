from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

from packlayer.client import PacklayerClient
from packlayer.config import load_config
from packlayer.domain.models import InstallOptions
from packlayer.config import PacklayerConfig
from packlayer.domain.exceptions import PacklayerError
from packlayer.cli.logging import setup as setup_logging
from packlayer.cli.theme import console, error, success


def main() -> None:
    args = _parse_args()
    setup_logging(verbose=args.verbose)
    config = load_config(Path(args.config) if args.config else None)

    dest = args.dest if args.dest is not None else Path(config.default_dest)
    options = InstallOptions(
        include_optional=not args.no_optional
        if args.no_optional
        else config.default_options.include_optional,
        side=args.side if args.side is not None else config.default_options.side,
    )

    try:
        asyncio.run(
            _install(
                args.source,
                dest,
                args.minecraft or config.minecraft_version,
                args.version,
                options,
                config,
            )
        )
    except PacklayerError as e:
        error(str(e))
        sys.exit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="packlayer",
        description="Minecraft modpack installer.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Path to a .toml config file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser(
        "install", help="Install a modpack from a .mrpack file, URL, or slug."
    )
    install.add_argument("source", help="Path, URL, Modrinth slug/URL, or ftb:<id>.")
    install.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Instance root directory (default: ./dest).",
    )
    install.add_argument(
        "--version",
        help="Modpack release version (e.g. 0.7.3).",
        default=None,
    )
    install.add_argument(
        "--minecraft",
        metavar="VERSION",
        default=None,
        help="Filter by Minecraft version (e.g. 1.20.1).",
    )
    install.add_argument(
        "--no-optional",
        action="store_true",
        default=False,
        help="Skip optional mods.",
    )
    install.add_argument(
        "--side",
        choices=["client", "server", "both"],
        default=None,
        help="Which side to install for (default: client).",
    )

    return parser.parse_args()


async def _install(
    source: str,
    dest: Path,
    minecraft_version: str | None,
    modpack_version: str | None,
    options: InstallOptions,
    config: PacklayerConfig,
) -> None:
    async with PacklayerClient(
        minecraft_version=minecraft_version,
        config=config,
    ) as client:
        with console.status(f"[info]resolving {source}[/info]"):
            modpack = await client.resolve(source, modpack_version=modpack_version)

        console.print(
            f"[name]{modpack.name}[/name] [version]{modpack.version}[/version]"
            f" — [count]{len(modpack.files)} files[/count]"
        )

        with Progress(
            TextColumn("[info]{task.description}[/info]"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("downloading", total=None)

            def on_start(total: int) -> None:
                progress.update(task, total=total)

            def on_progress() -> None:
                progress.advance(task)

            results = await client.install(
                modpack,
                dest,
                on_start=on_start,
                on_progress=on_progress,
                options=options,
            )

        success(
            f"{len(results.downloads)} mods, {results.override_count} overrides → {dest}"
        )
