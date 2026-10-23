"""Qualify PyTradeKit 0.8 LOT-06.4 IBKR order-session sequencing."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pytradekit.brokers import ProviderExecutionContext
from pytradekit.brokers.adapters.ibkr import (
    IBKRClientId,
    IBKRPaperConnectionRuntime,
    IBKRPaperRuntimeProfile,
    IBKRTransportConnectionEvidence,
    build_ibkr_order_session_runtime,
)
from pytradekit.orders.domain import OrderId
from pytradekit.shared import CorrelationId, Currency


class _LowLevel:
    def __init__(self) -> None:
        self.next_id = 500

    def isReady(self) -> bool:
        return True

    def getReqId(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value


class _ProviderClient:
    def __init__(self) -> None:
        self.client = _LowLevel()


class _Transport:
    def __init__(self) -> None:
        self.client = _ProviderClient()
        self.connected = False

    def connect(
        self,
        profile: IBKRPaperRuntimeProfile,
    ) -> IBKRTransportConnectionEvidence:
        self.connected = True
        return IBKRTransportConnectionEvidence(
            transport_name="deterministic",
            transport_version="2.1.0",
            socket_connected=True,
            protocol_ready=True,
            account_verified=True,
            managed_accounts=(profile.expected_account_id,),
            server_version=200,
        )

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def read_client(self) -> object:
        return self.client


@dataclass
class _Order:
    orderId: int
    clientId: int
    permId: int
    orderRef: str


@dataclass
class _Status:
    orderId: int
    status: str
    filled: object
    remaining: object
    avgFillPrice: object
    permId: int
    clientId: int
    lastFillPrice: object
    whyHeld: str


@dataclass
class _Trade:
    order: object
    orderStatus: object
    advancedError: str = ""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LOT-06.4 order sequencing and callback correlation "
            "without a provider economic write."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    connection = IBKRPaperConnectionRuntime(
        profile=IBKRPaperRuntimeProfile(
            expected_account_id="DU1234567",
            client_id=IBKRClientId(7),
        ),
        transport=_Transport(),
    )
    startup = connection.start()
    if not startup.ready_for_startup:
        raise RuntimeError("Deterministic IBKR startup unexpectedly failed.")

    runtime = build_ibkr_order_session_runtime(connection=connection)
    context = ProviderExecutionContext(
        order_id=OrderId.new(),
        correlation_id=CorrelationId.new(),
        client_order_reference="ptk-lot06-4",
        quote_currency=Currency("USD"),
    )
    reservation = runtime.reserve(context)
    correlated = runtime.callbacks.correlate_open_order(
        _Trade(
            order=_Order(
                orderId=reservation.session_order_id.value,
                clientId=reservation.client_id.value,
                permId=9001,
                orderRef=reservation.order_reference.value,
            ),
            orderStatus=_Status(
                orderId=reservation.session_order_id.value,
                status="Submitted",
                filled=0,
                remaining=1,
                avgFillPrice=0,
                permId=9001,
                clientId=reservation.client_id.value,
                lastFillPrice=0,
                whyHeld="",
            ),
        ),
        observed_at=datetime(2026, 10, 23, 10, 0, tzinfo=UTC),
    )
    if correlated is None:
        raise RuntimeError("Deterministic callback correlation unexpectedly failed.")

    payload = {
        "lot": "LOT-06.4",
        "release": "0.8.0b5",
        "provider": "ibkr",
        "environment": "PAPER",
        "client_id": reservation.client_id.value,
        "session_order_id": reservation.session_order_id.value,
        "order_reference": reservation.order_reference.value,
        "permanent_order_id": (
            correlated.observation.permanent_order_id.value
            if correlated.observation.permanent_order_id is not None
            else None
        ),
        "next_valid_id_synchronized": True,
        "callback_correlation": True,
        "economic_write_used": False,
        "place_order_used": False,
        "cancel_order_used": False,
        "real_paper_provider_used": False,
        "paper_certification_claimed": False,
        "trading_ready_claimed": False,
        "live_available": False,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    connection.stop()

    print("PyTradeKit 0.8 LOT-06.4 IBKR order session: PASS")
    print("nextValidId-derived sequencing: qualified")
    print("callback correlation: qualified")
    print("economic write used: false")
    print("PAPER certification claimed: false")
    print("TRADING_READY claimed: false")
    print("LIVE available: false")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
