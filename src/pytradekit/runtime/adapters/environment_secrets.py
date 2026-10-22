"""Environment-backed secret resolver for local and PAPER runtime use."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pytradekit.runtime.configuration import SecretRef
from pytradekit.runtime.errors import SecretResolutionError


class EnvironmentSecrets:
    """Resolve env:// references from a process environment mapping."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def resolve(self, reference: SecretRef) -> str:
        """Resolve an env:// secret reference and reject missing values."""

        if reference.scheme != "env":
            raise SecretResolutionError(
                f"EnvironmentSecrets cannot resolve scheme {reference.scheme!r}."
            )
        key = reference.locator.strip()
        if not key:
            raise SecretResolutionError("Environment secret reference has an empty locator.")
        value = self._environ.get(key, "")
        normalized = value.strip()
        if not normalized:
            raise SecretResolutionError(f"Required secret {reference} is missing.")
        return normalized

    def __repr__(self) -> str:
        """Return a representation that never includes secret values."""

        return "EnvironmentSecrets(source='environment')"
