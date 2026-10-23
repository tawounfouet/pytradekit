"""Unit tests for retained Alpaca PAPER compliance evidence."""

import json
from collections.abc import Mapping
from pathlib import Path

from pytradekit.brokers.adapters.alpaca.compliance_evidence import (
    AlpacaPaperEvidenceBundle,
)
from pytradekit.brokers.compliance import BrokerCapability

_EVIDENCE = Path(
    "docs/qualification/evidence/alpaca/v050-paper-20261022.json"
)


def _record() -> Mapping[str, object]:
    raw: object = json.loads(_EVIDENCE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return {str(key): value for key, value in raw.items()}


def test_retained_real_paper_record_parses_with_exact_provenance() -> None:
    bundle = AlpacaPaperEvidenceBundle.from_dict(_record())

    assert bundle.provenance.workflow_run_id == 39789766678
    assert bundle.provenance.artifact_id == 12430172671
    assert (
        bundle.provenance.artifact_json_sha256
        == "f4b271d0bf3148a8b400bdee6c10525d07b1ee5b033dc08f981a70c136ca1ab1"
    )
    assert bundle.provenance.qualified_commit == (
        "a7768911b56bb25a7efd24aae12f3cb032a5c9ef"
    )
    assert bundle.release_ready
    assert bundle.controlled_probe_passed
    assert bundle.deterministic_qualified


def test_real_paper_proof_is_capability_specific() -> None:
    bundle = AlpacaPaperEvidenceBundle.from_dict(_record())

    c3_capabilities = {
        BrokerCapability.ACCOUNT_QUERY,
        BrokerCapability.ORDER_QUERY,
        BrokerCapability.MARKET_ORDER,
        BrokerCapability.LIMIT_ORDER,
        BrokerCapability.CANCEL_ORDER,
        BrokerCapability.POSITION_QUERY,
        BrokerCapability.BALANCE_QUERY,
        BrokerCapability.CLIENT_ORDER_REFERENCE,
        BrokerCapability.EXECUTION_FACTS,
        BrokerCapability.RECONNECT_RECOVERY,
        BrokerCapability.LATEST_QUOTE,
    }
    assert all(bundle.paper_proof_passes(capability) for capability in c3_capabilities)
    assert not bundle.paper_proof_passes(BrokerCapability.PARTIAL_FILL)
    assert not bundle.paper_proof_passes(BrokerCapability.REPLACE_ORDER)


def test_retained_record_contains_no_raw_credential_fields() -> None:
    encoded = _EVIDENCE.read_text(encoding="utf-8").lower()

    assert "api_key" not in encoded
    assert "secret_key" not in encoded
    assert "password" not in encoded
    assert "bearer " not in encoded
