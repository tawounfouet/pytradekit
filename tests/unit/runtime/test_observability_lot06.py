"""LOT-06 metric cardinality and telemetry secret guards."""

from uuid import uuid4

import pytest

from pytradekit.runtime.observability import RuntimeMetrics, RuntimeObserver


def test_labeled_metrics_accept_low_cardinality_dimensions() -> None:
    metrics = RuntimeMetrics()
    metrics.increment_labeled(
        "authorization_decisions_total",
        labels={
            "permission": "SUBMIT_ORDER",
            "decision": "ALLOW",
            "environment": "PAPER",
        },
    )

    snapshot = metrics.snapshot()
    assert (
        snapshot.counters[
            "authorization_decisions_total{decision=ALLOW,environment=PAPER,"
            "permission=SUBMIT_ORDER}"
        ]
        == 1
    )


def test_metric_labels_reject_uuid_like_high_cardinality_values() -> None:
    metrics = RuntimeMetrics()

    with pytest.raises(ValueError, match="high-cardinality"):
        metrics.increment_labeled(
            "health_component_status",
            labels={"component": str(uuid4())},
        )


def test_metric_labels_reject_unapproved_label_names() -> None:
    metrics = RuntimeMetrics()

    with pytest.raises(ValueError, match="allowlist"):
        metrics.increment_labeled(
            "authorization_decisions_total",
            labels={"actor_id": "operator-1"},
        )


def test_operational_events_reject_secret_like_values() -> None:
    observer = RuntimeObserver()

    with pytest.raises(ValueError, match="secret"):
        observer.event(
            "unsafe",
            message="Authorization: Bearer should-not-appear",
        )
