"""The two §9.1 transitions milestone 4 needs: `proof_uploaded` and
`expire_hold`. The full transitions engine (`verify_eft`, `reject_eft`,
`accept_cash`, the generic `apply(order, action, actor, payload,
expected_status)` entry point §17.2 names) is milestone 5's job —
this module is deliberately narrow rather than a preview of that
dispatcher, so it doesn't have to guess `core.transitions`' shape before
milestone 5 actually specs it out. `verify_eft`/`reject_eft` in
particular need `expected_status`/`stale_state` handling (§8.6) for the
two-staff-race case; the two transitions here don't (a customer only
ever acts on their own order via its token, and a system job locks the
row it's about to change), so building that machinery early wouldn't
even get exercised yet.

`core/` has no HTTP imports (§17.2) — `EftError` carries an Appendix C
error `code` (plus whatever extra fields that code needs, e.g.
`retry_after_seconds`) rather than an HTTP response; the view layer
(`public/api.py`) maps it to a status code, same division as
`core.capacity.CapacityError`.
"""
from __future__ import annotations

import datetime as dt

from django.db import transaction

from .models import (
    ActorKind,
    Media,
    MediaKind,
    Order,
    OrderEvent,
    OrderStatus,
    Payment,
    PaymentStatus,
    ThrottleEvent,
    User,
)
from .tz import now_sast

# §9.1's `proof_uploaded` row: legal "From" statuses.
_PROOF_UPLOAD_FROM_STATUSES = frozenset({OrderStatus.AWAITING_EFT, OrderStatus.PAYMENT_REVIEW})

# §17.3: "5/hour/token".
PROOF_UPLOAD_THROTTLE_LIMIT = 5
PROOF_UPLOAD_THROTTLE_WINDOW = dt.timedelta(hours=1)
PROOF_UPLOAD_THROTTLE_SCOPE = "proof_token"


class EftError(Exception):
    def __init__(self, code: str, message: str, **extra: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


def check_proof_upload_throttle(public_token: str, *, now: dt.datetime | None = None) -> None:
    """Raises `EftError("throttled", ...)` past 5 attempts/hour/token.
    Deliberately doesn't record the attempt itself — call
    `record_proof_upload_attempt` only once the upload has passed
    `storage.service.validate_proof`, so a client that never sends a
    real file (or sends garbage) doesn't spend the customer's own
    throttle budget for them.
    """
    now = now or now_sast()
    window_start = now - PROOF_UPLOAD_THROTTLE_WINDOW
    count = ThrottleEvent.objects.filter(
        scope=PROOF_UPLOAD_THROTTLE_SCOPE, key=public_token, occurred_at__gte=window_start,
    ).count()
    if count >= PROOF_UPLOAD_THROTTLE_LIMIT:
        raise EftError(
            "throttled",
            "Too many upload attempts for this order — try again in a while.",
            retry_after_seconds=int(PROOF_UPLOAD_THROTTLE_WINDOW.total_seconds()),
        )


def record_proof_upload_attempt(public_token: str) -> None:
    ThrottleEvent.objects.create(scope=PROOF_UPLOAD_THROTTLE_SCOPE, key=public_token)


def record_proof_upload(
    order: Order,
    *,
    storage_key: str,
    mime_type: str,
    byte_size: int,
    sha256: bytes,
    actor_kind: str = ActorKind.CUSTOMER,
    actor_user: User | None = None,
    now: dt.datetime | None = None,
) -> Media:
    """§9.1's `proof_uploaded` row: `awaiting_eft`/`payment_review` ->
    `payment_review` either way, a new `media` row, `payments` repointed
    to it and set `under_review`. Locks the order row first — a
    double-submit of the upload control, or a race against the
    `expire_holds` job on the same order, both need the status
    check-then-set to be atomic, not just the two `.save()` calls.
    """
    now = now or now_sast()
    with transaction.atomic():
        # `of=("self",)`: lock only the `orders` row, not the joined
        # `payments` one — Postgres refuses `FOR UPDATE` across a reverse
        # OneToOneField's join (Django always emits it as a LEFT OUTER
        # JOIN there, since it can't prove a `Payment` always exists for
        # a given `Order`, even though `reserve()` guarantees it does in
        # practice) with "FOR UPDATE cannot be applied to the nullable
        # side of an outer join".
        locked = (
            Order.objects.select_for_update(of=("self",))
            .select_related("payment")
            .get(pk=order.pk)
        )
        if locked.status not in _PROOF_UPLOAD_FROM_STATUSES:
            raise EftError(
                "illegal_transition",
                "This order can no longer accept a proof of payment.",
            )

        media = Media.objects.create(
            kind=MediaKind.PROOF,
            storage_key=storage_key,
            mime_type=mime_type,
            byte_size=byte_size,
            sha256=sha256,
            order=locked,
        )

        from_status = locked.status
        payment: Payment = locked.payment
        payment.current_proof_media = media
        payment.proof_uploaded_at = now
        payment.status = PaymentStatus.UNDER_REVIEW
        payment.save(update_fields=["current_proof_media", "proof_uploaded_at", "status"])

        locked.status = OrderStatus.PAYMENT_REVIEW
        locked.save(update_fields=["status", "updated_at"])

        OrderEvent.objects.create(
            order=locked,
            from_status=from_status,
            to_status=OrderStatus.PAYMENT_REVIEW,
            action="proof_uploaded",
            actor_kind=actor_kind,
            actor_user=actor_user,
            payload={"media_id": media.pk, "mime_type": mime_type, "byte_size": byte_size},
        )
    return media


def expire_holds(*, now: dt.datetime | None = None, batch_size: int = 200) -> int:
    """§17.1's `expire_holds` job: every `awaiting_eft` order whose
    `hold_expires_at` has lapsed, released one at a time — "each in its
    own transaction" (§17.1) so one bad row can't sink the whole batch
    and no single lock is held across the full run. Never touches
    `payment_review` — a hold that lapsed after proof was already
    uploaded is edge case 6 (§20.4): stays `payment_review`, flagged for
    staff, not expired.
    """
    now = now or now_sast()
    stale_ids = list(
        Order.objects.filter(status=OrderStatus.AWAITING_EFT, hold_expires_at__lt=now)
        .order_by("hold_expires_at")
        .values_list("pk", flat=True)[:batch_size]
    )
    return sum(1 for order_id in stale_ids if _expire_one_hold(order_id, now=now))


def _expire_one_hold(order_id: int, *, now: dt.datetime) -> bool:
    with transaction.atomic():
        try:
            # `of=("self",)`: see the identical comment in
            # record_proof_upload above — same reverse-OneToOneField/
            # outer-join reason.
            order = (
                Order.objects.select_for_update(of=("self",))
                .select_related("payment")
                .get(pk=order_id)
            )
        except Order.DoesNotExist:
            return False
        # Recheck under lock: the batch above was selected outside any
        # lock, so a concurrent proof upload or (future, milestone 5)
        # reinstate could have already moved this order on.
        if order.status != OrderStatus.AWAITING_EFT:
            return False
        if order.hold_expires_at is None or order.hold_expires_at >= now:
            return False

        from_status = order.status
        order.status = OrderStatus.PAYMENT_EXPIRED
        order.save(update_fields=["status", "updated_at"])

        payment: Payment = order.payment
        payment.status = PaymentStatus.EXPIRED
        payment.save(update_fields=["status"])

        OrderEvent.objects.create(
            order=order,
            from_status=from_status,
            to_status=OrderStatus.PAYMENT_EXPIRED,
            action="expire_hold",
            actor_kind=ActorKind.SYSTEM,
            actor_user=None,
            payload={},
        )
    return True
