from __future__ import annotations
from typing import Optional

from packlayer.domain.exceptions import NoResolverFound
from packlayer.interfaces.resolver import ModpackResolver


class ResolverRegistry:
    """
    Ordered registry of :class:`~packlayer.interfaces.resolver.ModpackResolver` instances.

    Resolvers are queried in registration order — the first one whose
    :meth:`~ModpackResolver.can_handle` returns ``True`` wins. Register
    catch-all resolvers (like :class:`~packlayer.providers.modrinth.ModrinthResolver`)
    last so they don't shadow more specific ones.
    """

    def __init__(self, default_resolver: Optional[ModpackResolver] = None) -> None:
        self._resolvers: list[ModpackResolver] = []
        self._default = default_resolver

    def register(self, resolver: ModpackResolver) -> None:
        """Append a resolver to the end of the priority chain."""
        self._resolvers.append(resolver)

    def set_default_resolver(self, resolver: ModpackResolver) -> None:
        """Sets a default resolver if none could resolve correctly."""
        self._default = resolver

    def resolvers(self) -> list[ModpackResolver]:
        return list(self._resolvers)

    def pick(self, source: str) -> ModpackResolver:
        """
        Return the first resolver that can handle ``source``.

        Raises:
            NoResolverFound: No registered resolver accepted the source.
        """
        for resolver in self._resolvers:
            if resolver.can_handle(source):
                return resolver

        if self._default:
            return self._default

        raise NoResolverFound(source)
