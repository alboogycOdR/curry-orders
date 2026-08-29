"""Order numbers, `option_key` derivation, and line pricing — the parts of
§8.3's reservation transaction that are pure formatting/derivation rules
rather than the transaction itself (`core/capacity.py`).

`core/` has no HTTP imports (§17.2); nothing here touches the database.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date


def format_order_number(trading_day: date, seq: int) -> str:
    """`CT-YYMMDD-NNNN` (§8.3: `format('CT-%s-%04d', to_char(:date,
    'YYMMDD'), seq)`) — matches `orders.order_number`'s own CHECK
    constraint (`^CT-[0-9]{6}-[0-9]{4}$`) exactly. `seq` is
    `trading_days.next_order_seq` *before* incrementing (the caller reads
    it under the row's `FOR UPDATE` lock — that locking is
    `core.capacity`'s job, not this pure function's).
    """
    return f"CT-{trading_day.strftime('%y%m%d')}-{seq:04d}"


def generate_public_token() -> str:
    """A random token for `orders.public_token` — `secrets.token_urlsafe`
    gives URL-safe base64 with no separators to leak line breaks into a
    WhatsApp-shared link. 18 random bytes -> 24 characters, comfortably
    over the column's own `^.{22,}$` minimum-length CHECK (16 bytes would
    land exactly at 22, no margin for a future encoding-detail change).
    """
    return secrets.token_urlsafe(18)


def derive_option_key(selections: list[tuple[str, str]]) -> str:
    """D-29: `order_lines.option_key` is an ordinary application-set
    column (not a Postgres generated column, despite §7.10's wording —
    `schema_v1_1.sql` declares it plain `text`) — sorted
    `"Option=Value|..."`, computed here and set explicitly on every
    insert and on `amend_items`.

    `selections` is `[(option_name, value_name), ...]` for one order
    line, order-independent — sorted by option name so the same set of
    choices always derives the same key regardless of the order the
    customer picked them in or the order `DishOption` rows come back in.
    An option with no value selected (an optional add-on left unset)
    should simply be absent from `selections`, not passed as `("", "")`.
    """
    if not selections:
        return ""
    ordered = sorted(selections, key=lambda pair: pair[0])
    return "|".join(f"{option}={value}" for option, value in ordered)


@dataclass(frozen=True)
class LinePricing:
    unit_price_cents: int
    quantity: int
    line_total_cents: int


def price_line(base_price_cents: int, option_delta_cents: list[int], quantity: int) -> LinePricing:
    """Snapshot pricing for one order line (§11.6 step 2: "snapshot
    prices from current dishes / dish_option_values"). Unit price is the
    dish's current `price_cents` plus every selected option value's
    `price_delta_cents`; never the cart's cached price (§18.13) — the
    caller re-reads `Dish`/`DishOptionValue` inside the locked
    transaction (`core.capacity`) and passes the *current* values in
    here, this function does no DB lookups of its own.
    """
    unit_price_cents = base_price_cents + sum(option_delta_cents)
    return LinePricing(
        unit_price_cents=unit_price_cents,
        quantity=quantity,
        line_total_cents=unit_price_cents * quantity,
    )
