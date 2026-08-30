"""Small, independent session layer for customer accounts."""
from __future__ import annotations

import datetime as dt

from django.http import HttpRequest
from django.utils import timezone

from core.models import Customer

_CUSTOMER_ID_KEY = "customer_user_id"
_LOGIN_AT_KEY = "customer_login_at"
_LAST_SEEN_AT_KEY = "customer_last_seen_at"
ABSOLUTE_LIFETIME = dt.timedelta(hours=12)
IDLE_TIMEOUT = dt.timedelta(hours=2)


def log_in(request: HttpRequest, customer: Customer, now: dt.datetime | None = None) -> None:
    now = now or timezone.now()
    request.session.cycle_key()
    request.session[_CUSTOMER_ID_KEY] = customer.pk
    request.session[_LOGIN_AT_KEY] = now.isoformat()
    request.session[_LAST_SEEN_AT_KEY] = now.isoformat()


def log_out(request: HttpRequest) -> None:
    for key in (_CUSTOMER_ID_KEY, _LOGIN_AT_KEY, _LAST_SEEN_AT_KEY):
        request.session.pop(key, None)


def get_authenticated_customer(
    request: HttpRequest, now: dt.datetime | None = None
) -> Customer | None:
    now = now or timezone.now()
    customer_id = request.session.get(_CUSTOMER_ID_KEY)
    if customer_id is None:
        return None
    try:
        login_at = dt.datetime.fromisoformat(str(request.session.get(_LOGIN_AT_KEY)))
        last_seen = dt.datetime.fromisoformat(str(request.session.get(_LAST_SEEN_AT_KEY)))
        if now - login_at > ABSOLUTE_LIFETIME or now - last_seen > IDLE_TIMEOUT:
            raise ValueError
        customer = Customer.objects.get(pk=customer_id, anonymised_at__isnull=True)
    except (ValueError, TypeError, Customer.DoesNotExist):
        log_out(request)
        return None
    request.session[_LAST_SEEN_AT_KEY] = now.isoformat()
    return customer
