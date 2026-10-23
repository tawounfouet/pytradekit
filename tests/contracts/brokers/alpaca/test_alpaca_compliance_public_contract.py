"""Public import contract for Alpaca LOT-03 compliance certification."""

from pytradekit.brokers.adapters.alpaca import (
    ALPACA_EXPECTED_CERTIFICATION_LEVELS,
    ALPACA_REAL_PAPER_C3_CAPABILITIES,
    AlpacaPaperEvidenceBundle,
    build_alpaca_capability_manifest,
    build_alpaca_certification_run,
)


def test_alpaca_compliance_surface_is_public() -> None:
    assert ALPACA_REAL_PAPER_C3_CAPABILITIES
    assert ALPACA_EXPECTED_CERTIFICATION_LEVELS
    assert AlpacaPaperEvidenceBundle.__module__.endswith("compliance_evidence")
    assert callable(build_alpaca_capability_manifest)
    assert callable(build_alpaca_certification_run)
