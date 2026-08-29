"""Money formatting — integer cents (ZAR) to display string (spec §11.1:
`R 185.00`, space thousands separator, two decimals). All monetary
columns in schema_v1_1.sql (`price_cents`, `subtotal_cents`, ...) are
integer cents; this module never handles floats, on purpose.
"""
from __future__ import annotations


def format_cents(cents: int) -> str:
    """Format integer cents as e.g. `"R 185.00"` / `"R 1 000.00"`.

    Space-separated thousands, always two decimals, per spec §11.1.
    Negative values (e.g. a credit) render as `"-R 50.00"`.
    """
    sign = "-" if cents < 0 else ""
    whole_rand, sub_cents = divmod(abs(cents), 100)
    grouped = f"{whole_rand:,}".replace(",", " ")
    return f"{sign}R {grouped}.{sub_cents:02d}"
