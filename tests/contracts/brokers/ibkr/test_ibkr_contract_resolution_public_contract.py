"""Public contract for IBKR LOT-06.3 reference resolution."""

from pytradekit.brokers.adapters.ibkr import (
    IBKR_CONTRACT_REFERENCE_VERSION,
    IBAsyncContractRequestFactory,
    IBKRCanonicalInstrumentIdResolver,
    IBKRContractDetailsClient,
    IBKRContractReferenceResolver,
    IBKRContractRequestFactory,
    IBKRContractResolutionError,
    IBKRContractResolutionEvidence,
    IBKRRuntimeContractDetailsClient,
    StaticIBKRCanonicalInstrumentIdResolver,
    build_ibkr_contract_reference_resolver,
    normalize_ibkr_contract_details,
)


def test_ibkr_lot06_3_public_surface_is_exported() -> None:
    assert IBKR_CONTRACT_REFERENCE_VERSION == "0.8.0b4-lot06.3"
    assert IBAsyncContractRequestFactory.__name__ == (
        "IBAsyncContractRequestFactory"
    )
    assert IBKRCanonicalInstrumentIdResolver.__name__ == (
        "IBKRCanonicalInstrumentIdResolver"
    )
    assert IBKRContractDetailsClient.__name__ == "IBKRContractDetailsClient"
    assert IBKRContractReferenceResolver.__name__ == (
        "IBKRContractReferenceResolver"
    )
    assert IBKRContractRequestFactory.__name__ == (
        "IBKRContractRequestFactory"
    )
    assert issubclass(IBKRContractResolutionError, ValueError)
    assert IBKRContractResolutionEvidence.__name__ == (
        "IBKRContractResolutionEvidence"
    )
    assert IBKRRuntimeContractDetailsClient.__name__ == (
        "IBKRRuntimeContractDetailsClient"
    )
    assert StaticIBKRCanonicalInstrumentIdResolver.__name__ == (
        "StaticIBKRCanonicalInstrumentIdResolver"
    )
    assert callable(build_ibkr_contract_reference_resolver)
    assert callable(normalize_ibkr_contract_details)
