"""Property tests for Currency."""

from string import ascii_letters

from hypothesis import given
from hypothesis import strategies as st

from pytradekit.shared import Currency


@given(st.text(alphabet=ascii_letters, min_size=3, max_size=3))
def test_currency_normalization_is_canonical(code: str) -> None:
    currency = Currency(code)

    assert currency.code == code.upper()
    assert len(currency.code) == 3
    assert currency.code.isascii()
    assert currency.code.isalpha()
    assert currency.code.isupper()
