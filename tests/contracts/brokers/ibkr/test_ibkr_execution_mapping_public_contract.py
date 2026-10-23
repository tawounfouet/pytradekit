"""Public contract for IBKR SDK-free execution mapping."""

from pytradekit.brokers.adapters.ibkr import (
    IBKRExecutionDetailsObservation,
    IBKRExecutionDisposition,
    IBKRExecutionMappingError,
    IBKRExecutionRegistration,
    IBKRExecutionRegistry,
    IBKRExecutionSide,
    map_ibkr_execution_report,
    parse_ibkr_execution_time,
)


def test_ibkr_execution_mapping_surface_is_public() -> None:
    assert IBKRExecutionSide.BOUGHT.value == "BOT"
    assert IBKRExecutionSide.SOLD.value == "SLD"
    assert IBKRExecutionDisposition.NEW.value == "new"
    assert IBKRExecutionDisposition.DUPLICATE.value == "duplicate"
    assert IBKRExecutionDisposition.CORRECTION.value == "correction"
    assert IBKRExecutionDetailsObservation.__name__ == "IBKRExecutionDetailsObservation"
    assert IBKRExecutionRegistration.__name__ == "IBKRExecutionRegistration"
    assert IBKRExecutionRegistry.__name__ == "IBKRExecutionRegistry"
    assert issubclass(IBKRExecutionMappingError, ValueError)
    assert callable(parse_ibkr_execution_time)
    assert callable(map_ibkr_execution_report)
