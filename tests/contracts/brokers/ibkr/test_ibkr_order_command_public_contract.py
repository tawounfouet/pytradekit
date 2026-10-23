"""Public contract for IBKR SDK-free order command mapping."""

from pytradekit.brokers.adapters.ibkr import (
    IBKROrderAction,
    IBKROrderCommand,
    IBKROrderCommandError,
    IBKROrderType,
    IBKRPlacementCommand,
    IBKRTimeInForce,
    IBKRTransmitPolicy,
    map_ibkr_order_command,
)


def test_ibkr_order_command_surface_is_public() -> None:
    assert IBKROrderAction.BUY.value == "BUY"
    assert IBKROrderAction.SELL.value == "SELL"
    assert IBKROrderType.MARKET.value == "MKT"
    assert IBKROrderType.LIMIT.value == "LMT"
    assert IBKRTimeInForce.DAY.value == "DAY"
    assert IBKRTransmitPolicy.TRANSMIT.value == "TRANSMIT"
    assert IBKROrderCommand.__name__ == "IBKROrderCommand"
    assert IBKRPlacementCommand.__name__ == "IBKRPlacementCommand"
    assert issubclass(IBKROrderCommandError, ValueError)
    assert callable(map_ibkr_order_command)
