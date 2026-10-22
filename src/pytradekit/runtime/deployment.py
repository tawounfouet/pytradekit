"""Single-node deployment preflight and read-only health surface."""

from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from urllib.parse import urlparse

from pytradekit.persistence.database import (
    create_database_engine,
    database_is_healthy,
)
from pytradekit.runtime.configuration import RuntimeProfile
from pytradekit.runtime.deployment_security import RuntimeSecurityConfig
from pytradekit.runtime.errors import SecretResolutionError
from pytradekit.runtime.ports import SecretsPort


@dataclass(frozen=True, slots=True)
class DeploymentPreflightReport:
    """Sanitized deployment dependency report."""

    live: bool
    ready: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "live": self.live,
            "ready": self.ready,
            "reasons": list(self.reasons),
            "trading_ready": False,
        }


class DeploymentPreflight:
    """Verify required secrets and PostgreSQL without executing trading commands."""

    def __init__(
        self,
        *,
        profile: RuntimeProfile,
        secrets: SecretsPort,
        security: RuntimeSecurityConfig,
    ) -> None:
        self._profile = profile
        self._secrets = secrets
        self._security = security

    def liveness(self) -> DeploymentPreflightReport:
        """Return process-level liveness without claiming readiness."""

        return DeploymentPreflightReport(live=True, ready=False, reasons=())

    def readiness(self) -> DeploymentPreflightReport:
        """Fail closed if a required secret or durable-state dependency is unavailable."""

        try:
            self._secrets.resolve(self._profile.api_key_ref)
            self._secrets.resolve(self._profile.api_secret_ref)
            database_url = self._secrets.resolve(self._profile.database_url_ref)
        except SecretResolutionError:
            return DeploymentPreflightReport(
                live=True,
                ready=False,
                reasons=("REQUIRED_SECRET_UNAVAILABLE",),
            )

        if urlparse(database_url).scheme not in {
            "postgresql",
            "postgresql+psycopg",
        }:
            return DeploymentPreflightReport(
                live=True,
                ready=False,
                reasons=("DATABASE_URL_SCHEME_INVALID",),
            )

        try:
            engine = create_database_engine(
                database_url,
                require_tls=self._security.database_require_tls,
                connect_timeout_seconds=self._security.database_connect_timeout_seconds,
                statement_timeout_ms=self._security.database_statement_timeout_ms,
                pool_size=self._security.database_pool_size,
                max_overflow=self._security.database_max_overflow,
            )
            try:
                healthy = database_is_healthy(engine)
            finally:
                engine.dispose()
        except Exception:
            healthy = False

        if not healthy:
            return DeploymentPreflightReport(
                live=True,
                ready=False,
                reasons=("DATABASE_UNAVAILABLE",),
            )
        return DeploymentPreflightReport(live=True, ready=True, reasons=())


class _HealthRequestHandler(BaseHTTPRequestHandler):
    """Expose only read-only liveness and readiness endpoints."""

    preflight: ClassVar[DeploymentPreflight]

    def do_GET(self) -> None:
        if self.path == "/health/live":
            self._write_report(self.preflight.liveness())
            return
        if self.path == "/health/ready":
            self._write_report(self.preflight.readiness())
            return
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"not_found"}\n')

    def log_message(self, format: str, *args: object) -> None:
        _ = format
        _ = args

    def _write_report(self, report: DeploymentPreflightReport) -> None:
        payload = json.dumps(report.to_dict(), sort_keys=True).encode("utf-8") + b"\n"
        self.send_response(200 if report.ready or report.live and self.path.endswith("/live") else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve_health(
    *,
    preflight: DeploymentPreflight,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    """Serve the minimal read-only container health surface."""

    if not 1 <= port <= 65535:
        raise ValueError("Health server port must be between 1 and 65535.")
    handler = type(
        "ConfiguredHealthRequestHandler",
        (_HealthRequestHandler,),
        {"preflight": preflight},
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.serve_forever()
