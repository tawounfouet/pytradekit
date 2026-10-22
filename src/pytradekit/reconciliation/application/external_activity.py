"""External activity classification without guessing provenance."""

from dataclasses import dataclass

from pytradekit.reconciliation.domain import (
    CanonicalFill,
    CanonicalOrder,
    ExternalActivityOrigin,
)


@dataclass(frozen=True, slots=True)
class ExternalActivityClassification:
    """Evidence-preserving origin classification."""

    entity_type: str
    entity_id: str
    origin: ExternalActivityOrigin
    reason: str


class ExternalActivityClassifier:
    """Classify only what stable canonical identity proves."""

    def classify_order(
        self,
        order: CanonicalOrder,
    ) -> ExternalActivityClassification:
        if order.order_id is not None:
            return ExternalActivityClassification(
                entity_type="order",
                entity_id=str(order.order_id),
                origin=ExternalActivityOrigin.INTERNAL,
                reason="Provider order maps to a canonical PyTradeKit OrderId.",
            )
        identity = order.external_order_id or order.client_order_id
        if identity is None:
            raise AssertionError("CanonicalOrder requires a stable identity.")
        return ExternalActivityClassification(
            entity_type="order",
            entity_id=identity,
            origin=ExternalActivityOrigin.UNKNOWN_EXTERNAL,
            reason="No canonical order identity proves the origin.",
        )

    def classify_fill(
        self,
        fill: CanonicalFill,
    ) -> ExternalActivityClassification:
        origin: ExternalActivityOrigin
        if fill.origin is not ExternalActivityOrigin.INTERNAL:
            origin = fill.origin
        elif fill.order_id is not None:
            origin = ExternalActivityOrigin.INTERNAL
        else:
            origin = ExternalActivityOrigin.UNKNOWN_EXTERNAL
        return ExternalActivityClassification(
            entity_type="fill",
            entity_id=fill.external_fill_id,
            origin=origin,
            reason=(
                "Execution is linked to a canonical order."
                if origin is ExternalActivityOrigin.INTERNAL
                else "Execution origin is preserved as external until proven otherwise."
            ),
        )
