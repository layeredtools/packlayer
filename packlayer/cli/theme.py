from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

_THEME = Theme(
    {
        "info": "cyan",
        "muted": "dim",
        "success": "bold green",
        "error": "bold red",
        "name": "bold",
        "version": "dim",
        "path": "cyan",
        "count": "green",
    }
)

console = Console(theme=_THEME)


def info(msg: str) -> None:
    console.print(f"[info]{msg}[/info]")


def success(msg: str) -> None:
    console.print(f"[success]{msg}[/success]")


def error(msg: str) -> None:
    console.print(f"[error]{msg}[/error]")


def muted(msg: str) -> None:
    console.print(f"[muted]{msg}[/muted]")
