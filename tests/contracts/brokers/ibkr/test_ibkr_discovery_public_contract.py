"""Public contract for the IBKR LOT-04 discovery surface."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_DISCOVERY_VERSION,
    IBKR_PROVIDER_KEY,
    IBKRClientSurface,
    IBKRContractFreeze,
    build_ibkr_contract_freeze,
    validate_ibkr_paper_port,
)


def test_ibkr_discovery_surface_is_public() -> None:
    freeze = build_ibkr_contract_freeze()

    assert IBKR_PROVIDER_KEY == "ibkr"
    assert IBKR_DISCOVERY_VERSION == "1.0-rc1"
    assert isinstance(freeze, IBKRContractFreeze)
    assert freeze.runtime_surface is IBKRClientSurface.IB_GATEWAY
    assert callable(validate_ibkr_paper_port)
