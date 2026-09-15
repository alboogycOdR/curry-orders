"""Shared staff-session-granting logic.

Originally inline in `google_login_callback` (the `/manage/auth/google/
callback/` view) — extracted 2026-09-15 for the login-consolidation
decision: the customer-facing Google callback
(`public.views.customer_google_callback`, reached from the Account
tab) now calls this too, so *one* Google sign-in — from either entry
point — transparently also grants a staff session when the signed-in
email is on `StaffAllowlist`. Both callers get identical behaviour
(role sync, `SocialIdentity` linking, session creation) rather than
two copies that could drift.

Made properly bidirectional 2026-09-15 (same day, follow-up fix): this
now *also* grants a customer session when the same Google identity is
already linked to a `Customer` — signing in as staff shouldn't leave
someone looking logged-out on the Account tab if they're also a
customer under the same Google account. Found live: a stray test
`SocialIdentity` row (this developer's own leftover test data, not a
real user) was squatting on a staff account's `staff_user` OneToOne
slot, so the *real* identity's own `staff_user` backfill kept silently
failing (correctly swallowed — see below — so it never broke login,
but nothing downstream of that fenced-off block ran either). The fix:
look up the identity plainly, and check it for a linked customer,
*outside* the fenced-off bookkeeping block — the customer-session grant
must never depend on that bookkeeping succeeding.
"""
from __future__ import annotations

import datetime as dt

from django.db import IntegrityError, transaction
from django.http import HttpRequest

from core.models import SocialIdentity, StaffAllowlist, User


def try_grant_staff_session(
    request: HttpRequest, *, email: str, sub: str, name: str, now: dt.datetime,
    picture: str = "",
) -> bool:
    """If `email` (already Google-verified by the caller) is on
    `StaffAllowlist`, get-or-create the matching `core.User`, keep its
    role (and Google avatar, when `picture` is given) in sync, link/
    record the `SocialIdentity`, and log them into a staff session —
    alongside whatever session state already exists on this same
    request (e.g. a customer session already established by the
    caller). Returns `True` if staff access was granted, `False` if
    this email simply isn't staff — not an error case; that's the
    outcome for nearly every customer sign-in.
    """
    email = email.lower()
    try:
        entry = StaffAllowlist.objects.get(email=email)
    except StaffAllowlist.DoesNotExist:
        return False

    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "name": name or email,
            "role": entry.role,
            "password_hash": "",
            "must_change_password": False,
            "active": True,
            "google_avatar_url": picture,
        },
    )
    if not user.active:
        return False

    # A Google-verified name is more trustworthy than whatever's on
    # file (e.g. a placeholder set before this account ever signed in
    # with Google) — keep it in sync on every Google sign-in, not just
    # at creation. Same fix, same reasoning, as the analogous
    # Customer.full_name bug found and fixed earlier today
    # (public.views.account_setup) — get_or_create's `defaults` only
    # ever apply on create, so an existing row's name silently never
    # updated without this.
    update_fields = []
    if name and user.name != name:
        user.name = name
        update_fields.append("name")
    if user.role != entry.role:
        user.role = entry.role
        update_fields.append("role")
    if picture and user.google_avatar_url != picture:
        user.google_avatar_url = picture
        update_fields.append("google_avatar_url")
    if update_fields:
        user.save(update_fields=update_fields)

    # Plain lookup first, kept outside the fenced-off bookkeeping block
    # below — everything that follows (the customer-session check) must
    # work even if the staff_user backfill fails.
    identity = SocialIdentity.objects.filter(provider="google", uid=sub).first()

    # SocialIdentity is unique on (provider, uid) *and* staff_user is
    # its own OneToOneField (one linked identity per staff account) —
    # a caller that already ran its own customer-side get_or_create on
    # this exact (provider, uid) may have created the row already this
    # same request; get_or_create's `defaults` only apply on create, so
    # backfill staff_user explicitly if it's an existing row that
    # doesn't have it yet. Wrapped in its own savepoint and never
    # allowed to block granting the session below: this is bookkeeping
    # (which SocialIdentity row a staff account happens to be recorded
    # against), not a precondition for authentication — the User row
    # and role are already resolved above regardless of what happens
    # here. A real IntegrityError here (this user's staff_user slot
    # already taken by a *different* uid — e.g. a stale/test row, or a
    # second Google account someone mistakenly tries) should never 500
    # a login.
    try:
        with transaction.atomic():
            identity, created = SocialIdentity.objects.get_or_create(
                provider="google", uid=sub, defaults={"email": email, "staff_user": user},
            )
            if not created and identity.staff_user_id != user.pk:
                identity.staff_user = user
                identity.save(update_fields=["staff_user"])
    except IntegrityError:
        pass

    # Bidirectional consolidation: this same Google identity may already
    # be linked to a Customer (e.g. from an earlier Account-tab sign-in,
    # or vice versa) — grant that session too, regardless of whether the
    # staff_user bookkeeping above succeeded.
    if identity is not None and identity.customer_id:
        customer = identity.customer
        if customer.anonymised_at is None:
            from public import customer_sessions
            customer_sessions.log_in(request, customer)

    from staff.sessions import log_in as staff_log_in
    staff_log_in(request, user, now)
    return True
