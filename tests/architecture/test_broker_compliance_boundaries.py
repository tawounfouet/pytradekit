"""Architecture fitness functions for milestone 0.8 broker compliance LOT-01."""

from typing import get_type_hints

from pytradekit.brokers import (
    ProviderAccountIdentity,
    ProviderExecutionContext,
    ProviderInstrumentIdentity,
    ProviderOrderIdentity,
)
from pytradekit.orders.domain import OrderId
from tests.architecture._imports import imported_modules, python_sources


def _concrete_provider_literals(path_fragment: str) -> list[str]:
    offenders: list[str] = []
    for path in python_sources():
        if path_fragment not in path.as_posix():
            continue
        source = path.read_text(encoding="utf-8").lower()
        if '"alpaca"' in source or "'alpaca'" in source:
            offenders.append(f"{path}: alpaca")
        if '"ibkr"' in source or "'ibkr'" in source:
            offenders.append(f"{path}: ibkr")
    return offenders


def test_ff_048_provider_sdk_imports_are_confined_to_provider_adapters() -> None:
    offenders: list[str] = []
    for path in python_sources():
        for imported in imported_modules(path):
            if imported == "alpaca" or imported.startswith("alpaca."):
                if "/brokers/adapters/alpaca/" not in path.as_posix():
                    offenders.append(f"{path}: {imported}")
    assert not offenders, "Provider SDK imports escaped adapter boundary:\n" + "\n".join(
        offenders
    )


def test_ff_049_compliance_core_imports_no_concrete_adapter() -> None:
    offenders: list[str] = []
    for path in python_sources():
        if "/brokers/compliance/" not in path.as_posix():
            continue
        for imported in imported_modules(path):
            if imported.startswith("pytradekit.brokers.adapters"):
                offenders.append(f"{path}: {imported}")
    assert not offenders, "Concrete adapter imports found in compliance core:\n" + "\n".join(
        offenders
    )


def test_ff_050_domain_cannot_inspect_concrete_provider_name() -> None:
    offenders = _concrete_provider_literals("/domain/")
    assert not offenders, "Concrete provider names found in Domain:\n" + "\n".join(offenders)


def test_ff_051_oms_cannot_inspect_concrete_provider_name() -> None:
    offenders = _concrete_provider_literals("/orders/")
    assert not offenders, "Concrete provider names found in OMS:\n" + "\n".join(offenders)


def test_ff_052_risk_cannot_inspect_concrete_provider_name() -> None:
    offenders = _concrete_provider_literals("/risk/")
    assert not offenders, "Concrete provider names found in Risk:\n" + "\n".join(offenders)


def test_ff_053_portfolio_cannot_inspect_concrete_provider_name() -> None:
    offenders = _concrete_provider_literals("/portfolio/")
    assert not offenders, "Concrete provider names found in Portfolio:\n" + "\n".join(offenders)


def test_ff_054_reconciliation_domain_cannot_inspect_concrete_provider_name() -> None:
    offenders = _concrete_provider_literals("/reconciliation/domain/")
    assert not offenders, "Concrete provider names found in Reconciliation Domain:\n" + "\n".join(
        offenders
    )


def test_ff_055_safety_cannot_inspect_concrete_provider_name() -> None:
    offenders = _concrete_provider_literals("/safety/")
    assert not offenders, "Concrete provider names found in Safety:\n" + "\n".join(offenders)


def test_ff_056_provider_ids_remain_external_evidence() -> None:
    assert get_type_hints(ProviderOrderIdentity)["external_order_id"] is str
    assert get_type_hints(ProviderAccountIdentity)["external_account_id"] is str
    assert get_type_hints(ProviderInstrumentIdentity)["external_id"] is str
    assert get_type_hints(ProviderExecutionContext)["order_id"] is OrderId
