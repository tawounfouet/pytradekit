"""Minimal PyTradeKit 0.1 foundations demonstration."""

from datetime import UTC, datetime
from decimal import Decimal

from pytradekit.reference import AssetClass, Instrument
from pytradekit.shared import Currency, InstrumentId, Price, Quantity
from pytradekit.testing import FakeClock


def main() -> None:
    """Demonstrate deterministic, provider-neutral financial primitives."""
    usd = Currency("USD")
    instrument = Instrument(
        id=InstrumentId.new(),
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        quote_currency=usd,
    )
    price = Price(Decimal("192.50"), usd)
    quantity = Quantity(Decimal("10"))
    clock = FakeClock.at(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    notional = price * quantity

    print(f"instrument: {instrument.symbol}")
    print(f"price: {price}")
    print(f"quantity: {quantity}")
    print(f"notional: {notional}")
    print(f"clock: {clock.now().isoformat()}")


if __name__ == "__main__":
    main()
