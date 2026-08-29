"""Staff-facing views. Kitchen desk only this pass — see public/views.py's
module docstring for the same "visual pass only" framing; it applies here
too.

**Known gap, deliberately left open this pass:** the design handoff is
explicit that the kitchen desk "must be behind auth — it exposes customer
names and the day's takings" (README §4). It isn't, here. Staff auth
(D-12: email+password, Argon2id, session rules — spec §4) is the other
half of milestone 1 and was explicitly out of scope for this session (the
owner steered this pass to the visual/Broadsheet work specifically).
`core.User` has no Django auth wiring yet (see its docstring), so there is
no real session to gate this behind — bolting on `@login_required` against
Django's own unrelated default auth would just add a second, throwaway
auth path that the real staff-auth milestone would then have to unpick.
Do not deploy this route publicly before that milestone lands.
"""
from __future__ import annotations

import datetime as dt

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.models import Settings
from core.tz import now_sast


def _time(value: dt.time | str) -> dt.time:
    """See `public/views.py`'s identical helper — `Settings`'s TimeField
    defaults are "HH:MM" strings, only parsed to `datetime.time` on
    save/refresh-from-db, so an unsaved `Settings.current()` fallback
    (pre-seed) hands back the raw string.
    """
    if isinstance(value, str):
        return dt.datetime.strptime(value, "%H:%M").time()
    return value

_DAY_NAMES_FULL = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
_MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Sample-only run sheet (handoff README §4 "Today's run") — a real version
# is `core.Order`/`core.Payment` rows for the trading day, joined to slots,
# with `advance` as a POST through `core.transitions.apply()` (milestone
# 5/6, spec §12.4/§9). `si` = status index into STATUSES below, matching
# the handoff's own STATUS[]/STATUS_TAG[] arrays and its forward-only
# advance() reducer.
_STATUSES = ["Awaiting payment", "Confirmed", "Cooking", "Ready", "Collected"]
_STATUS_TAG_CLASS = {
    "Awaiting payment": "tag tag-outline",
    "Confirmed": "tag tag-accent",
    "Cooking": "tag tag-accent-2",
    "Ready": "tag tag-accent",
    "Collected": "tag tag-neutral",
}
_SAMPLE_ORDERS = [
    {"ref": "1041", "who": "Naledi M.", "items": "2× Chicken Gatsby", "slot": "16:00",
     "pay": "EFT", "value": "R 190.00", "si": 4},
    {"ref": "1042", "who": "Riaan P.", "items": "1× Full House", "slot": "16:15",
     "pay": "Cash", "value": "R 130.00", "si": 3},
    {"ref": "1043", "who": "Thandi K.", "items": "3× Chicken Roti Roll", "slot": "16:30",
     "pay": "EFT", "value": "R 195.00", "si": 2},
    {"ref": "1044", "who": "Fatima D.", "items": "1× Beef Lasagne, 1× Steak Curry", "slot": "17:00",
     "pay": "EFT", "value": "R 185.00", "si": 1},
    {"ref": "1045", "who": "Josh v/d B.", "items": "2× Steak Masala Gatsby", "slot": "17:30",
     "pay": "Cash", "value": "R 200.00", "si": 0},
    {"ref": "1046", "who": "Ayanda S.", "items": "1× Chicken Curry & Roti", "slot": "17:45",
     "pay": "EFT", "value": "R 85.00", "si": 0},
]


def kitchen(request: HttpRequest) -> HttpResponse:
    settings = Settings.current()
    today = now_sast().date()
    today_label = f"{_DAY_NAMES_FULL[today.weekday()]} {today.day} {_MONTH_NAMES[today.month - 1]}"
    service_window = (
        f"{_time(settings.default_window_start).strftime('%H:%M')}"
        f"–{_time(settings.default_window_end).strftime('%H:%M')}"
    )
    orders = [
        {**o, "status": _STATUSES[o["si"]], "tag_class": _STATUS_TAG_CLASS[_STATUSES[o["si"]]]}
        for o in _SAMPLE_ORDERS
    ]
    return render(request, "staff/kitchen.html", {
        "today_label": today_label,
        "service_window": service_window,
        "orders": orders,
        "statuses": _STATUSES,
        "status_tag_class": _STATUS_TAG_CLASS,
        # Sample-only capacity meters (handoff README §4) — real figures
        # are `core.Order`/`core.Payment` aggregates for the trading day
        # against `Settings`/`TradingDay` ceilings (milestone 6, §8.2).
        "meter_orders": {"value": 18, "of": 24, "label": "of 24 orders secured"},
        "meter_cash": {"value": "R 420", "of": "R 600", "label": "of R 600 cash ceiling"},
        "meter_dish": {"value": 12, "of": 20, "label": "of 20 Gatsby loaves left"},
    })
