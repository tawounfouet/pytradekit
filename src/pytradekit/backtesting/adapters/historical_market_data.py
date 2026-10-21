"""Deterministic historical market data adapter."""

from collections.abc import Iterator
from datetime import datetime
from hashlib import sha256

from pytradekit.backtesting.clock import BacktestClock
from pytradekit.market_data.domain import HistoricalDataset, MarketDataEvent
from pytradekit.shared import DomainValidationError, InstrumentId


def historical_events_checksum(events: tuple[MarketDataEvent, ...]) -> str:
    """Hash canonical event semantics in deterministic order."""
    lines: list[str] = []
    for event in events:
        bar = event.bar
        lines.append(
            "|".join(
                (
                    str(bar.instrument_id),
                    bar.interval,
                    str(bar.open.value),
                    str(bar.high.value),
                    str(bar.low.value),
                    str(bar.close.value),
                    str(bar.volume.value) if bar.volume is not None else "",
                    bar.start_time.isoformat(),
                    bar.end_time.isoformat(),
                    str(event.source_sequence),
                )
            )
        )
    return sha256("\n".join(lines).encode("utf-8")).hexdigest()


class HistoricalMarketDataAdapter:
    """Validate and expose only already-emitted historical events."""

    def __init__(
        self,
        *,
        dataset: HistoricalDataset,
        events: tuple[MarketDataEvent, ...],
        clock: BacktestClock,
    ) -> None:
        self._dataset = dataset
        self._events = events
        self._clock = clock
        self._validate()

    def iter_events(
        self,
        *,
        instruments: tuple[InstrumentId, ...] | None = None,
    ) -> Iterator[MarketDataEvent]:
        requested = set(instruments) if instruments is not None else None
        for event in self._events:
            if requested is not None and event.instrument_id not in requested:
                continue
            self._clock.advance_to(event.event_time)
            yield event

    def _validate(self) -> None:
        if not self._events:
            raise DomainValidationError("Historical dataset must contain at least one event.")
        if historical_events_checksum(self._events) != self._dataset.checksum:
            raise DomainValidationError("Historical dataset checksum mismatch.")

        previous_key: tuple[datetime, str, str, int] | None = None
        seen: set[tuple[InstrumentId, str, datetime]] = set()
        allowed = set(self._dataset.instruments)
        for event in self._events:
            bar = event.bar
            if bar.instrument_id not in allowed:
                raise DomainValidationError(
                    "Historical event instrument is not in dataset manifest."
                )
            if bar.interval != self._dataset.interval:
                raise DomainValidationError(
                    "Historical event interval does not match dataset manifest."
                )
            if not (self._dataset.start_time <= event.event_time <= self._dataset.end_time):
                raise DomainValidationError("Historical event is outside dataset time range.")
            duplicate_key = (bar.instrument_id, bar.interval, bar.end_time)
            if duplicate_key in seen:
                raise DomainValidationError("Duplicate historical bar detected.")
            seen.add(duplicate_key)
            key = (
                event.event_time,
                str(event.instrument_id),
                "bar",
                event.source_sequence,
            )
            if previous_key is not None and key <= previous_key:
                raise DomainValidationError("Historical events must be strictly ordered.")
            previous_key = key
