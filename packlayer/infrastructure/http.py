from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from packlayer.domain.config import RetryConfig
from packlayer.domain.exceptions import NetworkError
from packlayer.interfaces.http import HttpClient
from packlayer._version import __version__

logger = logging.getLogger("packlayer.http")

_CHUNK = 64 * 1024
_USER_AGENT = f"packlayer/{__version__} (github.com/teilorr/packlayer)"


class PacklayerHTTP(HttpClient):
    def __init__(self, retry: RetryConfig | None = None) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._retry = retry or RetryConfig()

    async def __aenter__(self) -> PacklayerHTTP:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={"User-Agent": _USER_AGENT},
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def get_json(
        self,
        url: str,
        params: dict | None = None,
        headers: dict[str, str] | None = None,
        json: dict | None = None,
    ) -> Any:
        method = "POST" if json is not None else "GET"
        async with await self._request(
            method, url, params=params, headers=headers, json=json
        ) as resp:
            return await resp.json()

    async def get_bytes(self, url: str) -> bytes:
        async with await self._request("GET", url) as resp:
            return await resp.read()

    async def get_stream(self, url: str) -> AsyncIterator[bytes]:
        if not self._session:
            raise RuntimeError("PacklayerHTTP must be used as an async context manager")

        retry = self._retry
        for attempt in range(retry.max_retries):
            try:
                async with self._session.request("GET", url) as resp:
                    if resp.status not in retry.retryable_statuses:
                        resp.raise_for_status()
                        async for chunk in resp.content.iter_chunked(_CHUNK):
                            yield chunk
                        return

                    wait = float(
                        resp.headers.get("Retry-After", retry.backoff_base**attempt)
                    )
                    logger.warning(f"{resp.status} {url} — retrying in {wait:.1f}s")
                    await resp.release()
                    await asyncio.sleep(wait)

            except aiohttp.ClientError as e:
                if attempt == retry.max_retries - 1:
                    logger.debug(
                        f"exception type={type(e).__name__!r} str={str(e)!r} repr={repr(e)}"
                    )
                    raise NetworkError(f"{e} ({url})" if str(e) else url) from e

        raise NetworkError(f"failed after {retry.max_retries} retries: {url}")

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> aiohttp.ClientResponse:
        if not self._session:
            raise RuntimeError("PacklayerHTTP must be used as an async context manager")

        retry = self._retry
        last_conn_exc: aiohttp.ClientConnectionError | None = None

        for attempt in range(retry.max_retries):
            logger.debug(f"{method} {url} (attempt {attempt + 1}/{retry.max_retries})")

            try:
                resp = await self._session.request(method, url, **kwargs)
            except aiohttp.ClientConnectionError as e:
                last_conn_exc = e
                wait = retry.backoff_base**attempt
                logger.warning(f"connection error {url} — retrying in {wait:.1f}s")
                await asyncio.sleep(wait)
                continue

            if resp.status not in retry.retryable_statuses:
                try:
                    resp.raise_for_status()
                except aiohttp.ClientResponseError as e:
                    raise NetworkError(f"{e.status} {e.message}: {url}") from e
                return resp

            wait = float(resp.headers.get("Retry-After", retry.backoff_base**attempt))
            logger.warning(f"{resp.status} {url} — retrying in {wait:.1f}s")
            await resp.release()
            await asyncio.sleep(wait)

        if last_conn_exc is not None:
            msg = str(last_conn_exc)
            raise NetworkError(f"{msg} ({url})" if msg else url) from last_conn_exc

        raise NetworkError(f"failed after {retry.max_retries} retries: {url}")
