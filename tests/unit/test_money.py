"""Unit tests for core/money.py — spec §11.1: 'R 185.00', space thousands,
two decimals."""
from __future__ import annotations

import pytest

from core.money import format_cents


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (18500, "R 185.00"),
        (0, "R 0.00"),
        (50, "R 0.50"),
        (100, "R 1.00"),
        (100000, "R 1 000.00"),
        (123456789, "R 1 234 567.89"),
        (1, "R 0.01"),
        (99, "R 0.99"),
    ],
)
def test_format_cents(cents: int, expected: str) -> None:
    assert format_cents(cents) == expected


def test_format_cents_negative() -> None:
    assert format_cents(-18500) == "-R 185.00"
