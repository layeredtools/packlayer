from __future__ import annotations

from dataclasses import dataclass, field
from packlayer.domain.models import InstallOptions


@dataclass
class RetryConfig:
    max_retries: int = 5
    backoff_base: float = 2.0
    retryable_statuses: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )


@dataclass
class PacklayerConfig:
    concurrency: int = 8
    minecraft_version: str | None = None
    default_dest: str = "./dest"
    default_options: InstallOptions = field(default_factory=InstallOptions)
    retry: RetryConfig = field(default_factory=RetryConfig)
