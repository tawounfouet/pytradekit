"""Minimal tracing export boundary."""

from typing import Protocol

from pytradekit.operations.domain import TraceRecord


class TraceExporterPort(Protocol):
    """Export one completed trace record."""

    def export(self, record: TraceRecord) -> None:
        ...
