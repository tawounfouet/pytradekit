"""Architecture checks for the controlled public root API."""

import pytradekit


def test_ff_005_root_exports_are_controlled() -> None:
    assert pytradekit.__all__ == ["__version__"]


def test_domain_types_are_not_promoted_to_root_package() -> None:
    forbidden_names = (
        "Currency",
        "Money",
        "Price",
        "Quantity",
        "Percentage",
        "Instrument",
        "ContractSpecification",
        "SystemClock",
        "FakeClock",
    )

    assert all(not hasattr(pytradekit, name) for name in forbidden_names)
