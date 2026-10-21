"""Contract tests for supported 0.1 package imports."""

from pytradekit import __version__
from pytradekit.reference import (
    AssetClass,
    ContractSpecification,
    Instrument,
    InstrumentId,
    InstrumentMapping,
)
from pytradekit.runtime import ClockPort, SystemClock
from pytradekit.shared import (
    CausationId,
    CorrelationId,
    Currency,
    DomainEvent,
    EventId,
    Money,
    Percentage,
    Price,
    Quantity,
)
from pytradekit.testing import FakeClock, InstrumentBuilder


def test_supported_public_imports_are_available() -> None:
    exports = (
        __version__,
        AssetClass,
        ContractSpecification,
        Instrument,
        InstrumentId,
        InstrumentMapping,
        ClockPort,
        SystemClock,
        CausationId,
        CorrelationId,
        Currency,
        DomainEvent,
        EventId,
        Money,
        Percentage,
        Price,
        Quantity,
        FakeClock,
        InstrumentBuilder,
    )

    assert all(export is not None for export in exports)
