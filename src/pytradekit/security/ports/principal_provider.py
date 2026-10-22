"""Authenticated principal provider port."""

from typing import Protocol

from pytradekit.security.domain import AuthenticatedPrincipal


class PrincipalProvider(Protocol):
    """Resolve the principal authenticated by an external boundary."""

    def current_principal(self) -> AuthenticatedPrincipal:
        ...
