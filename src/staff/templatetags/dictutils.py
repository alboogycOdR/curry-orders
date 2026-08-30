"""`{{ some_dict|get_item:some_key }}` — Django templates have no `[]`
lookup for a plain dict keyed by a variable (only the `.` accessor,
which only works for a string/int literal key or an attribute/method
name). Used by `staff/inbox.html` to look up `slots_by_day[trading_day_id]`.
"""
from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="get_item")
def get_item(mapping: dict, key: object) -> object:
    try:
        return mapping.get(key)
    except AttributeError:
        return None
