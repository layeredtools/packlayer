# packlayer/config.py
from __future__ import annotations
from pathlib import Path
import tomllib
from packlayer.domain.config import PacklayerConfig, RetryConfig
from packlayer.domain.models import InstallOptions

_SEARCH = [
    Path(".packlayer.toml"),
    Path("packlayer.toml"),
    Path.home() / ".config" / "packlayer" / "config.toml",
]


def load_config(path: Path | None = None) -> PacklayerConfig:
    candidates = [path] if path else _SEARCH
    for p in candidates:
        if p and p.exists():
            with p.open("rb") as f:
                raw = tomllib.load(f)
            return _parse(raw)
    return PacklayerConfig()


def _parse(raw: dict) -> PacklayerConfig:
    install = raw.get("install", {})
    retry = raw.get("retry", {})
    return PacklayerConfig(
        concurrency=raw.get("concurrency", 8),
        minecraft_version=raw.get("minecraft_version"),
        default_dest=install.get("dest", "./mods"),
        default_options=InstallOptions(
            side=install.get("side", "client"),
            include_optional=install.get("include_optional", True),
        ),
        retry=RetryConfig(
            max_retries=retry.get("max_retries", 5),
            backoff_base=retry.get("backoff_base", 2.0),
            retryable_statuses=frozenset(
                retry.get("retryable_statuses", [429, 500, 502, 503, 504])
            ),
        ),
    )
