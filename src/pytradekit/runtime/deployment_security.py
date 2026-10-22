"""Production-like runtime security configuration for PAPER deployments."""

from dataclasses import dataclass
from urllib.parse import urlparse

from pytradekit.runtime.errors import RuntimeConfigurationError

ALPACA_PAPER_TRADING_ENDPOINT = "https://paper-api.alpaca.markets"
ALPACA_DATA_ENDPOINT = "https://data.alpaca.markets"
ALPACA_TRADE_STREAM_ENDPOINT = "wss://paper-api.alpaca.markets/stream"


@dataclass(frozen=True, slots=True)
class RuntimeSecurityConfig:
    """Non-secret operational security controls for one runtime process."""

    startup_timeout_seconds: float = 30.0
    shutdown_timeout_seconds: float = 15.0
    telemetry_flush_timeout_seconds: float = 5.0
    database_require_tls: bool = True
    database_connect_timeout_seconds: int = 5
    database_statement_timeout_ms: int = 5000
    database_pool_size: int = 5
    database_max_overflow: int = 5

    def __post_init__(self) -> None:
        if self.startup_timeout_seconds <= 0:
            raise RuntimeConfigurationError("Startup timeout must be positive.")
        if self.shutdown_timeout_seconds <= 0:
            raise RuntimeConfigurationError("Shutdown timeout must be positive.")
        if self.telemetry_flush_timeout_seconds <= 0:
            raise RuntimeConfigurationError("Telemetry flush timeout must be positive.")
        if self.database_connect_timeout_seconds <= 0:
            raise RuntimeConfigurationError("Database connect timeout must be positive.")
        if self.database_statement_timeout_ms <= 0:
            raise RuntimeConfigurationError("Database statement timeout must be positive.")
        if self.database_pool_size <= 0:
            raise RuntimeConfigurationError("Database pool size must be positive.")
        if self.database_max_overflow < 0:
            raise RuntimeConfigurationError(
                "Database max overflow must be non-negative."
            )

    @classmethod
    def production_like(cls) -> "RuntimeSecurityConfig":
        """Return the hardened single-node PAPER defaults."""

        return cls(database_require_tls=True)

    @classmethod
    def local_development(cls) -> "RuntimeSecurityConfig":
        """Return local defaults where a developer PostgreSQL may not expose TLS."""

        return cls(database_require_tls=False)


def validate_alpaca_paper_endpoints(
    *,
    trading_endpoint: str,
    data_endpoint: str,
    stream_endpoint: str,
) -> None:
    """Allow only the explicit Alpaca PAPER and data endpoints qualified by 0.7."""

    expected = (
        ("trading", trading_endpoint, ALPACA_PAPER_TRADING_ENDPOINT, "https"),
        ("data", data_endpoint, ALPACA_DATA_ENDPOINT, "https"),
        ("stream", stream_endpoint, ALPACA_TRADE_STREAM_ENDPOINT, "wss"),
    )
    for name, raw, allowed, required_scheme in expected:
        normalized = raw.strip()
        parsed = urlparse(normalized)
        if parsed.scheme != required_scheme:
            raise RuntimeConfigurationError(
                f"Alpaca {name} endpoint must use {required_scheme}."
            )
        if normalized != allowed:
            raise RuntimeConfigurationError(
                f"Alpaca {name} endpoint is not an approved PAPER endpoint."
            )
        if parsed.username is not None or parsed.password is not None:
            raise RuntimeConfigurationError(
                f"Alpaca {name} endpoint must not contain credentials."
            )
