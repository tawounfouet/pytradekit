"""Property qualification for SecretRef fail-closed validation."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pytradekit.runtime import SecretRef
from pytradekit.runtime.errors import RuntimeConfigurationError


@given(
    value=st.sampled_from(
        [
            "",
            "API_KEY",
            "env://",
            "://missing",
            "1env://API_KEY",
            "env://API_KEY\nINJECTED",
            "env://API_KEY\x00",
        ]
    )
)
def test_invalid_secret_references_are_rejected(value: str) -> None:
    with pytest.raises(RuntimeConfigurationError):
        SecretRef(value)
