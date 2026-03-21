import pytest

from app.utils import base62


def test_base62_roundtrip() -> None:
    for n in (0, 1, 61, 62, 1000, 10**9):
        assert base62.decode(base62.encode(n)) == n


def test_base62_invalid_char() -> None:
    with pytest.raises(ValueError):
        base62.decode("!")
