from __future__ import annotations

import logging

from rich.logging import RichHandler

from packlayer.cli.theme import console

logger = logging.getLogger("packlayer")


def setup(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=verbose, markup=True)],
    )
    logger.setLevel(level)
