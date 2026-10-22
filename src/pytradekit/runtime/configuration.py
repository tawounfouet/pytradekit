"""Runtime configuration primitives for the persistent PAPER runtime."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from pytradekit.runtime.errors import RuntimeConfigurationError


_SECRET_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*$")


class RuntimeEnvironment(StrEnum):
    """Runtime environments supported by the 0.5 configuration contract."""

    PAPER = "PAPER"


@dataclass(frozen=True, slots=True)
class SecretRef:
    """Opaque reference to a secret resolved through SecretsPort."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip() if isinstance(self.value, str) else ""
        if not normalized:
            raise RuntimeConfigurationError("SecretRef value must be a non-empty string.")
        if "://" not in normalized:
            raise RuntimeConfigurationError(
                "SecretRef must include an explicit scheme such as env://."
            )
        scheme, locator = normalized.split("://", 1)
        if not _SECRET_SCHEME.fullmatch(scheme.lower()):
            raise RuntimeConfigurationError("SecretRef scheme is invalid.")
        if not locator.strip():
            raise RuntimeConfigurationError("SecretRef locator must not be empty.")
        if any(character in normalized for character in ("\n", "\r", "\x00")):
            raise RuntimeConfigurationError("SecretRef contains invalid control characters.")
        object.__setattr__(self, "value", normalized)

    @property
    def scheme(self) -> str:
        """Return the reference scheme."""

        return self.value.split("://", 1)[0].lower()

    @property
    def locator(self) -> str:
        """Return the scheme-specific locator."""

        return self.value.split("://", 1)[1]

    def __str__(self) -> str:
        """Return the opaque reference, not the resolved secret."""

        return self.value


def mask_account_id(value: str) -> str:
    """Mask a provider account identifier for diagnostics."""

    normalized = value.strip()
    if len(normalized) <= 4:
        return "*" * len(normalized)
    return f"{'*' * (len(normalized) - 4)}{normalized[-4:]}"


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeProfile:
    """Provider-neutral bootstrap profile for the 0.5 PAPER runtime."""

    name: str
    provider: str
    environment: RuntimeEnvironment
    expected_account_id: str
    api_key_ref: SecretRef
    api_secret_ref: SecretRef
    database_url_ref: SecretRef
    market_data_feed: str = "iex"
    trading_endpoint: str = "https://paper-api.alpaca.markets"
    data_endpoint: str = "https://data.alpaca.markets"
    stream_endpoint: str = "wss://paper-api.alpaca.markets/stream"

    def __post_init__(self) -> None:
        name = self.name.strip() if isinstance(self.name, str) else ""
        provider = self.provider.strip().lower() if isinstance(self.provider, str) else ""
        account_id = (
            self.expected_account_id.strip()
            if isinstance(self.expected_account_id, str)
            else ""
        )
        feed = (
            self.market_data_feed.strip().lower()
            if isinstance(self.market_data_feed, str)
            else ""
        )

        if not name:
            raise RuntimeConfigurationError("RuntimeProfile name must not be empty.")
        if provider != "alpaca":
            raise RuntimeConfigurationError(
                "PyTradeKit 0.5 runtime profile supports provider 'alpaca' only."
            )
        if self.environment is not RuntimeEnvironment.PAPER:
            raise RuntimeConfigurationError(
                "PyTradeKit 0.5 runtime profile is hard-locked to PAPER."
            )
        if not account_id:
            raise RuntimeConfigurationError(
                "RuntimeProfile expected_account_id must not be empty."
            )
        if feed != "iex":
            raise RuntimeConfigurationError(
                "PyTradeKit 0.5 Alpaca market data feed is hard-locked to 'iex'."
            )

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "expected_account_id", account_id)
        object.__setattr__(self, "market_data_feed", feed)

        from pytradekit.runtime.deployment_security import (
            validate_alpaca_paper_endpoints,
        )

        validate_alpaca_paper_endpoints(
            trading_endpoint=self.trading_endpoint,
            data_endpoint=self.data_endpoint,
            stream_endpoint=self.stream_endpoint,
        )

    @property
    def masked_account_id(self) -> str:
        """Return the provider account identifier in masked form."""

        return mask_account_id(self.expected_account_id)

    def __repr__(self) -> str:
        """Return a diagnostic representation without the full account identifier."""

        return (
            "RuntimeProfile("
            f"name={self.name!r}, "
            f"provider={self.provider!r}, "
            f"environment={self.environment.value!r}, "
            f"expected_account_id={self.masked_account_id!r}, "
            f"api_key_ref={self.api_key_ref!s}, "
            f"api_secret_ref={self.api_secret_ref!s}, "
            f"database_url_ref={self.database_url_ref!s}, "
            f"market_data_feed={self.market_data_feed!r}, "
            f"trading_endpoint={self.trading_endpoint!r}, "
            f"data_endpoint={self.data_endpoint!r}, "
            f"stream_endpoint={self.stream_endpoint!r}"
            ")"
        )

    @classmethod
    def alpaca_paper_from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> RuntimeProfile:
        """Build the hard-locked Alpaca PAPER profile from environment configuration."""

        source = os.environ if environ is None else environ

        environment_raw = _required(source, "PYTRADEKIT_RUNTIME_ENVIRONMENT").upper()
        try:
            environment = RuntimeEnvironment(environment_raw)
        except ValueError as exc:
            raise RuntimeConfigurationError(
                "PYTRADEKIT_RUNTIME_ENVIRONMENT must be PAPER for PyTradeKit 0.5."
            ) from exc

        return cls(
            name=source.get("PYTRADEKIT_RUNTIME_PROFILE", "alpaca-paper").strip()
            or "alpaca-paper",
            provider="alpaca",
            environment=environment,
            expected_account_id=_required(
                source,
                "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID",
            ),
            api_key_ref=SecretRef(
                source.get(
                    "PYTRADEKIT_ALPACA_API_KEY_REF",
                    "env://PYTRADEKIT_ALPACA_PAPER_API_KEY",
                )
            ),
            api_secret_ref=SecretRef(
                source.get(
                    "PYTRADEKIT_ALPACA_SECRET_KEY_REF",
                    "env://PYTRADEKIT_ALPACA_PAPER_SECRET_KEY",
                )
            ),
            database_url_ref=SecretRef(
                source.get(
                    "PYTRADEKIT_DATABASE_URL_REF",
                    "env://PYTRADEKIT_DATABASE_URL",
                )
            ),
            market_data_feed=source.get("PYTRADEKIT_ALPACA_DATA_FEED", "iex"),
            trading_endpoint=source.get(
                "PYTRADEKIT_ALPACA_TRADING_ENDPOINT",
                "https://paper-api.alpaca.markets",
            ),
            data_endpoint=source.get(
                "PYTRADEKIT_ALPACA_DATA_ENDPOINT",
                "https://data.alpaca.markets",
            ),
            stream_endpoint=source.get(
                "PYTRADEKIT_ALPACA_STREAM_ENDPOINT",
                "wss://paper-api.alpaca.markets/stream",
            ),
        )


def _required(source: Mapping[str, str], key: str) -> str:
    value = source.get(key, "")
    normalized = value.strip()
    if not normalized:
        raise RuntimeConfigurationError(f"Required runtime setting {key} is missing.")
    return normalized
