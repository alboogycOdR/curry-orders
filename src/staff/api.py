"""The one staff JSON API endpoint this pass builds: `POST
/manage/api/orders/:id/transition` (spec §17.3's staff table) — backs
the EFT payment queue's row actions (§12.3, `static/js/payments.js`).
Session-authed (`staff.sessions`) + CSRF, same as every other staff POST
in this project; the `{% csrf_token %}` on `staff/payments.html` is what
puts the cookie this endpoint's caller reads.

A single generic endpoint rather than one route per action, matching
`core.transitions.apply()`'s own single-dispatcher shape (§17.2) and the
spec's literal `{action, expected_status, reason?, payload?}` body —
every action this pass implements (§9.1's fifteen non-checkout,
non-EFT-upload rows) is reachable through it, even the ones with no
staff UI yet (see `core/transitions.py`'s module docstring); only the
EFT queue actually calls it today.
"""
from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from core.models import ActorKind, Order
from core.transitions import Actor, TransitionError, apply

from .decorators import staff_login_required

# Appendix C's own table, same split public/api.py's checkout endpoint
# uses — everything not listed here is a 422 (a §8.2-style capacity
# ceiling bridged from CapacityError by core.transitions.apply() itself,
# e.g. `slot_full`/`dish_qty_exceeded` from `reinstate`/`amend_items`).
# `not_found` isn't an Appendix C code (that table is domain/rule
# failures only) but needs a real status too.
_ERROR_STATUS = {
    "stale_state": 409,
    "illegal_transition": 409,
    "reason_required": 403,
    "owner_only": 403,
    "validation_error": 400,
    "not_found": 404,
}


def _error_response(code: str, message: str, **extra: object) -> JsonResponse:
    status = _ERROR_STATUS.get(code, 422)
    return JsonResponse({"error": code, "message": message, **extra}, status=status)


@staff_login_required
@require_POST
@csrf_protect
def transition(request: HttpRequest, order_id: int) -> JsonResponse:
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return _error_response("not_found", "No such order.")

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return _error_response("validation_error", "Malformed JSON body.")

    action = data.get("action")
    expected_status = data.get("expected_status")
    if not isinstance(action, str) or not isinstance(expected_status, str):
        return _error_response(
            "validation_error", "action and expected_status are required.",
        )
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        return _error_response("validation_error", "reason must be a string.")
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        return _error_response("validation_error", "payload must be an object.")

    actor = Actor(kind=ActorKind.STAFF, user=request.staff_user)
    try:
        order = apply(order, action, actor, expected_status, reason=reason, payload=payload)
    except TransitionError as exc:
        return _error_response(exc.code, exc.message, **exc.extra)

    return JsonResponse({"order_number": order.order_number, "status": order.status})
