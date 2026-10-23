"""LOT-04 qualification for the dependency-free IBKR contract freeze."""

from pytradekit.brokers.adapters.ibkr import (
    IBKRClientSurface,
    IBKRContractOutcome,
    build_ibkr_contract_freeze,
    validate_ibkr_paper_port,
)


def test_lot04_freezes_ib_gateway_paper_without_core_change() -> None:
    freeze = build_ibkr_contract_freeze()

    assert freeze.provider == "ibkr"
    assert freeze.environment.value == "PAPER"
    assert freeze.runtime_surface is IBKRClientSurface.IB_GATEWAY
    assert validate_ibkr_paper_port(
        surface=IBKRClientSurface.IB_GATEWAY,
        port=4002,
    ) == 4002
    assert not freeze.broker_neutral_core_change_required


def test_lot04_freezes_stable_identity_semantics() -> None:
    freeze = build_ibkr_contract_freeze()

    assert freeze.client_reference_field == "orderRef"
    assert freeze.session_order_id_field == "orderId"
    assert freeze.external_order_id_field == "permId"
    assert freeze.external_fill_id_field == "execId"
    assert freeze.external_instrument_id_field == "conId"


def test_lot04_reconnect_requires_explicit_reconciliation() -> None:
    freeze = build_ibkr_contract_freeze()
    by_subject = {decision.subject: decision for decision in freeze.decisions}

    reconnect = by_subject["adapter:reconnect"]
    assert reconnect.outcome is IBKRContractOutcome.ADAPTER_LOCAL
    assert "reconciliation" in reconnect.decision.lower()
    assert freeze.reconnect_resubmit_setting.endswith("=false")


def test_lot04_makes_no_provider_certification_claim() -> None:
    freeze = build_ibkr_contract_freeze()

    assert freeze.unresolved_paper_questions
    assert all(
        decision.outcome.name != "UNCHANGED" or decision.subject.startswith("core:")
        for decision in freeze.decisions
        if decision.subject.startswith("core:")
    )
