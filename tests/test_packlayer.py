from __future__ import annotations

import pytest
import pytest_asyncio

from packlayer import PacklayerClient
from packlayer.domain.exceptions import NoResolverFound, SlugNotFound, NoVersionFound
from packlayer.domain.models import InstallOptions, Modpack, ModpackVersion
from packlayer.interfaces.resolver import ModpackResolver


_FAKE_PACKS: dict[str, Modpack] = {
    "hello": Modpack(
        name="Hello Pack",
        version="1.0.0",
        minecraft_version="1.20.1",
        files=(),
    ),
    "world": Modpack(
        name="World Pack",
        version="2.0.0",
        minecraft_version="1.21.0",
        files=(),
    ),
}

_FAKE_VERSIONS: dict[str, list[ModpackVersion]] = {
    "hello": [
        ModpackVersion(
            id="fake-0002",
            version_number="1.0.0",
            name="1.0.0",
            loaders=("fabric",),
            game_versions=("1.20.1",),
            date_published="2024-06-01T00:00:00Z",
        ),
        ModpackVersion(
            id="fake-0001",
            version_number="0.9.0",
            name="0.9.0",
            loaders=("fabric",),
            game_versions=("1.19.4",),
            date_published="2024-01-01T00:00:00Z",
        ),
    ],
}


class FakeResolver(ModpackResolver):
    """Handles ``test:<name>`` sources. No network calls."""

    def can_handle(self, source: str) -> bool:
        return source.startswith("test:")

    async def resolve(
        self, source: str, *, modpack_version: str | None = None
    ) -> Modpack:
        name = source.removeprefix("test:")
        if name not in _FAKE_PACKS:
            raise SlugNotFound(name)
        pack = _FAKE_PACKS[name]
        if modpack_version and pack.version != modpack_version:
            raise NoVersionFound(name, None)
        return pack

    async def fetch_versions(self, source: str) -> list[ModpackVersion]:
        name = source.removeprefix("test:")
        if name not in _FAKE_VERSIONS:
            raise SlugNotFound(name)
        return _FAKE_VERSIONS[name]


@pytest_asyncio.fixture
async def client():
    async with PacklayerClient(extra_resolvers=[FakeResolver()]) as c:
        yield c


@pytest_asyncio.fixture
async def plain_client():
    """Client with no extra resolvers."""
    async with PacklayerClient() as c:
        yield c


class TestPluginSystem:
    def test_resolver_order(self, client: PacklayerClient) -> None:
        names = [type(r).__name__ for r in client.resolvers()]
        assert names[0] == "FakeResolver", "extra_resolvers must be registered first"

    def test_resolver_for_fake(self, client: PacklayerClient) -> None:
        assert isinstance(client.resolver_for("test:hello"), FakeResolver)

    def test_resolver_for_modrinth(self, client: PacklayerClient) -> None:
        from packlayer.providers.modrinth.resolver import ModrinthResolver

        assert isinstance(
            client.resolver_for("mr:fabulously-optimized"), ModrinthResolver
        )

    def test_resolver_for_ftb(self, client: PacklayerClient) -> None:
        from packlayer.providers.ftb.resolver import FTBResolver

        assert isinstance(client.resolver_for("ftb:79"), FTBResolver)

    def test_no_resolver_found(self, client: PacklayerClient) -> None:
        with pytest.raises(NoResolverFound):
            client.resolver_for("unknown://something")

    def test_fake_takes_priority_over_builtins(self, client: PacklayerClient) -> None:
        assert type(client.resolver_for("test:hello")).__name__ == "FakeResolver"

    @pytest.mark.asyncio
    async def test_resolve(self, client: PacklayerClient) -> None:
        modpack = await client.resolve("test:hello")
        assert modpack.name == "Hello Pack"
        assert modpack.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_resolve_all_packs(self, client: PacklayerClient) -> None:
        for key, expected in _FAKE_PACKS.items():
            modpack = await client.resolve(f"test:{key}")
            assert modpack.name == expected.name

    @pytest.mark.asyncio
    async def test_resolve_pinned_version(self, client: PacklayerClient) -> None:
        modpack = await client.resolve("test:hello", modpack_version="1.0.0")
        assert modpack.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_resolve_pinned_version_not_found(
        self, client: PacklayerClient
    ) -> None:
        with pytest.raises(NoVersionFound):
            await client.resolve("test:hello", modpack_version="99.0.0")

    @pytest.mark.asyncio
    async def test_resolve_slug_not_found(self, client: PacklayerClient) -> None:
        with pytest.raises(SlugNotFound):
            await client.resolve("test:doesnotexist")

    @pytest.mark.asyncio
    async def test_list_versions(self, client: PacklayerClient) -> None:
        versions = await client.list_versions("test:hello")
        assert len(versions) == 2
        assert versions[0].version_number == "1.0.0"
        assert versions[1].version_number == "0.9.0"


class TestInstallOptions:
    def test_defaults(self) -> None:
        opts = InstallOptions()
        assert opts.include_optional is True
        assert opts.side == "client"

    def test_server_side(self) -> None:
        assert InstallOptions(side="server").side == "server"

    def test_both_side(self) -> None:
        assert InstallOptions(side="both").side == "both"

    def test_no_optional(self) -> None:
        assert InstallOptions(include_optional=False).include_optional is False


class TestModrinth:
    @pytest.mark.asyncio
    async def test_list_versions(self, plain_client: PacklayerClient) -> None:
        versions = await plain_client.list_versions("mr:fabulously-optimized")
        assert len(versions) > 0
        assert all(v.version_number for v in versions)

    @pytest.mark.asyncio
    async def test_resolve_latest(self, plain_client: PacklayerClient) -> None:
        modpack = await plain_client.resolve("mr:fabulously-optimized")
        assert modpack.name
        assert modpack.minecraft_version
        assert len(modpack.files) > 0

    @pytest.mark.asyncio
    async def test_resolve_pinned(self, plain_client: PacklayerClient) -> None:
        versions = await plain_client.list_versions("mr:fabulously-optimized")
        pinned = versions[-1].version_number
        modpack = await plain_client.resolve(
            "mr:fabulously-optimized", modpack_version=pinned
        )
        assert modpack.version == pinned

    @pytest.mark.asyncio
    async def test_resolve_url(self, plain_client: PacklayerClient) -> None:
        modpack = await plain_client.resolve(
            "https://modrinth.com/modpack/fabulously-optimized"
        )
        assert modpack.name

    @pytest.mark.asyncio
    async def test_slug_not_found(self, plain_client: PacklayerClient) -> None:
        with pytest.raises(SlugNotFound):
            await plain_client.resolve("mr:this-pack-does-not-exist-xyz")


class TestFTB:
    @pytest.mark.asyncio
    async def test_list_versions(self, plain_client: PacklayerClient) -> None:
        versions = await plain_client.list_versions("ftb:79")
        assert len(versions) > 0

    @pytest.mark.asyncio
    async def test_resolve_latest(self, plain_client: PacklayerClient) -> None:
        modpack = await plain_client.resolve("ftb:79")
        assert modpack.name
        assert modpack.minecraft_version
        assert len(modpack.files) > 0

    @pytest.mark.asyncio
    async def test_resolve_pinned(self, plain_client: PacklayerClient) -> None:
        versions = await plain_client.list_versions("ftb:79")
        pinned = versions[-1].version_number
        modpack = await plain_client.resolve("ftb:79", modpack_version=pinned)
        assert modpack.version == pinned

    @pytest.mark.asyncio
    async def test_pack_not_found(self, plain_client: PacklayerClient) -> None:
        with pytest.raises(NoVersionFound):
            await plain_client.resolve("ftb:999999999")
