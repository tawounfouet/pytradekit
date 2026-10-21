"""Immutable historical dataset manifest."""

from dataclasses import dataclass
from datetime import datetime

from pytradekit.shared import DomainValidationError, InstrumentId, require_utc_datetime


@dataclass(frozen=True, slots=True)
class HistoricalDataset:
    """Versioned identity and metadata for one immutable historical dataset."""

    dataset_id: str
    version: str
    checksum: str
    instruments: tuple[InstrumentId, ...]
    interval: str
    start_time: datetime
    end_time: datetime
    timezone: str = "UTC"
    schema_version: str = "1"
    adjustment_mode: str = "RAW"
    source: str = "local"

    def __post_init__(self) -> None:
        for field_name, value in (
            ("dataset_id", self.dataset_id),
            ("version", self.version),
            ("interval", self.interval),
            ("timezone", self.timezone),
            ("schema_version", self.schema_version),
            ("adjustment_mode", self.adjustment_mode),
            ("source", self.source),
        ):
            if not isinstance(value, str) or not value.strip():
                raise DomainValidationError(f"HistoricalDataset {field_name} must be non-empty.")
        if not isinstance(self.checksum, str) or len(self.checksum) != 64:
            raise DomainValidationError("HistoricalDataset checksum must be a SHA-256 hex digest.")
        try:
            int(self.checksum, 16)
        except ValueError as exc:
            raise DomainValidationError("HistoricalDataset checksum must be hexadecimal.") from exc
        if not self.instruments or not all(
            isinstance(item, InstrumentId) for item in self.instruments
        ):
            raise DomainValidationError("HistoricalDataset requires InstrumentId values.")
        start = require_utc_datetime(self.start_time, field_name="HistoricalDataset start_time")
        end = require_utc_datetime(self.end_time, field_name="HistoricalDataset end_time")
        if start >= end:
            raise DomainValidationError("HistoricalDataset start_time must be before end_time.")
