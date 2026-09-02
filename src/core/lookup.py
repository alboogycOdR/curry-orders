"""Order lookup (spec §11.10, milestone 9) — order number + mobile,
throttled via the same `throttle_events` table M7's EFT proof-upload
throttle (`core.eft`) uses, just two different scopes
(`ThrottleEvent`'s own docstring already names `lookup_ip`/
`lookup_order` among its scope vocabulary).

`core/` has no HTTP imports (§17.2) — `LookupError` carries an Appendix
C-style `code` rather than an HTTP response; the view layer
(`public/views.py`) maps it to a generic on-screen message (never a
distinct one per failure reason — §11.10: "Failures return a generic
message", no account-enumeration leak).
"""
from __future__ import annotations

import datetime as dt
import re

from .models import Order, ThrottleEvent
from .tz import now_sast

# §11.10 / §17.3: "10/hour/IP and 10/hour/order number".
LOOKUP_THROTTLE_LIMIT = 10
LOOKUP_THROTTLE_WINDOW = dt.timedelta(hours=1)
LOOKUP_IP_SCOPE = "lookup_ip"
LOOKUP_ORDER_SCOPE = "lookup_order"


class LookupError(Exception):
    def __init__(self, code: str, message: str, **extra: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


# Task 7: canonicalize CT-YYMMDD-NNNN variants (dashes optional, any case).
_CT_CANONICAL = re.compile(r"^[Cc][Tt]-?(\d{6})-?(\d{4})$")


def normalize_order_number(raw: str) -> str:
    """`CT-…` case-insensitive (§11.10) — stripped, canonicalized to
    ``CT-YYMMDD-NNNN`` when the pattern matches (dashes optional, any
    case), upper-cased only for everything else.  Non-CT inputs (e.g.
    ``RC-…``) pass through as upper-case and fail the DB lookup cleanly
    — no ``RC-`` alias exists and none will be created (PLAN.md D-01).
    """
    s = raw.strip()
    m = _CT_CANONICAL.match(s)
    if m:
        return f"CT-{m.group(1)}-{m.group(2)}"
    return s.upper()


def last9_digits(raw: str) -> str:
    """§11.10: "mobile (any accepted format, matched on last 9 digits of
    E.164)" — deliberately more lenient than `core.phone.normalize_sa_mobile`
    (which would reject a landline or a slightly-malformed number outright);
    lookup only needs enough of the number to compare against the order's
    own stored E.164 snapshot, not a fully valid mobile number.
    """
    digits = re.sub(r"\D", "", raw or "")
    return digits[-9:] if len(digits) >= 9 else ""


def check_lookup_throttle(ip: str, order_number: str, *, now: dt.datetime | None = None) -> None:
    """Raises `LookupError("throttled", ...)` past either ceiling.
    Deliberately doesn't record the attempt itself — see
    `record_lookup_attempt`'s own docstring for why that's a separate
    call.
    """
    now = now or now_sast()
    window_start = now - LOOKUP_THROTTLE_WINDOW
    ip_count = ThrottleEvent.objects.filter(
        scope=LOOKUP_IP_SCOPE, key=ip, occurred_at__gte=window_start,
    ).count()
    if ip_count >= LOOKUP_THROTTLE_LIMIT:
        raise LookupError(
            "throttled", "Too many attempts — try again in a while.",
            retry_after_seconds=int(LOOKUP_THROTTLE_WINDOW.total_seconds()),
        )
    # Only check order-scope throttle when an order number was provided.
    if order_number:
        order_count = ThrottleEvent.objects.filter(
            scope=LOOKUP_ORDER_SCOPE, key=normalize_order_number(order_number),
            occurred_at__gte=window_start,
        ).count()
        if order_count >= LOOKUP_THROTTLE_LIMIT:
            raise LookupError(
                "throttled", "Too many attempts — try again in a while.",
                retry_after_seconds=int(LOOKUP_THROTTLE_WINDOW.total_seconds()),
            )


def record_lookup_attempt(ip: str, order_number: str) -> None:
    """Recorded for *every* attempt (match or not) — unlike
    `core.eft`'s proof-upload throttle (which only spends budget on a
    file that actually validated), a lookup attempt is exactly what
    needs to be rate-limited regardless of outcome: a wrong-mobile guess
    against a real order number is the attack this throttle exists for.
    """
    ThrottleEvent.objects.create(scope=LOOKUP_IP_SCOPE, key=ip)
    # Only record order-scope when an order number was provided.
    if order_number:
        ThrottleEvent.objects.create(
            scope=LOOKUP_ORDER_SCOPE, key=normalize_order_number(order_number),
        )


def find_orders_by_mobile(mobile_raw: str, limit: int = 5) -> list[Order]:
    """Return the `limit` most-recent orders whose stored E.164 mobile
    ends with the last 9 digits of `mobile_raw`. Returns [] when mobile
    is blank or nothing matches — callers cannot distinguish "no orders"
    from "invalid mobile", preserving the same no-enumeration guarantee
    as `find_order`.
    """
    wanted = last9_digits(mobile_raw)
    if not wanted:
        return []
    return list(
        Order.objects.filter(customer_mobile_snapshot__endswith=wanted)
        .select_related("trading_day")
        .order_by("-created_at")[:limit]
    )


def find_order(order_number: str, mobile_raw: str) -> Order | None:
    """`None` on any mismatch — order-not-found and mobile-not-matching
    are indistinguishable to the caller, by design (§11.10's own
    "generic message" rule).
    """
    order = Order.objects.filter(order_number__iexact=normalize_order_number(order_number)).first()
    if order is None:
        return None
    wanted = last9_digits(mobile_raw)
    if not wanted or order.customer_mobile_snapshot[-9:] != wanted:
        return None
    return order
