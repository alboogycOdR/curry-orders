"""`{{ price_cents|cents }}` — renders integer cents as `"R 185.00"`
(spec §11.1) via `core.money.format_cents`, so templates never do
cents-to-rand arithmetic (or worse, string-concatenate `"R " ~
price_cents`) themselves.
"""
from __future__ import annotations

from django import template

from core.money import format_cents

register = template.Library()


@register.filter(name="cents")
def cents_filter(value: object) -> str:
    try:
        return format_cents(int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
