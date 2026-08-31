"""Five-dot order tracker for the public status page (Task 7, PR 7).

One dot per stage; dots up to and including the active stage are filled.
Terminal statuses (collected, expired, cancelled) return ``None`` from
``step_data()`` — the caller replaces the stepper with a terminal-state
display rather than showing the progress bar.
"""
from __future__ import annotations

from core.models import OrderStatus

# Labels shown under each dot, left to right.
STEPS: list[str] = [
    "Order received",
    "Payment",
    "Confirmed",
    "Cooking",
    "Ready to collect",
]

# Statuses where the stepper is replaced entirely by the terminal state.
TERMINAL_STATUSES: frozenset[str] = frozenset({
    OrderStatus.COLLECTED,
    OrderStatus.PAYMENT_EXPIRED,
    OrderStatus.CANCELLED,
})

# All other active statuses (used by the view to decide meta refresh).
NON_TERMINAL_STATUSES: frozenset[str] = frozenset({
    OrderStatus.AWAITING_EFT,
    OrderStatus.PAYMENT_REVIEW,
    OrderStatus.CASH_REQUEST,
    OrderStatus.CONFIRMED_PREP,
    OrderStatus.CASH_DUE,
    OrderStatus.IN_KITCHEN,
    OrderStatus.READY,
})

# Status → active step index (0-based).
# All steps up to and including `active` get `filled=True`.
_STATUS_STEP: dict[str, int] = {
    OrderStatus.AWAITING_EFT:   1,
    OrderStatus.PAYMENT_REVIEW: 1,
    OrderStatus.CASH_REQUEST:   2,
    OrderStatus.CONFIRMED_PREP: 2,
    OrderStatus.CASH_DUE:       2,
    OrderStatus.IN_KITCHEN:     3,
    OrderStatus.READY:          4,
}


def step_data(status: str) -> list[dict] | None:
    """Return a list of step dicts for the five-dot stepper, or ``None``
    for terminal statuses (caller replaces the stepper entirely).

    Each dict::

        {"label": str, "filled": bool, "active": bool}

    *filled* → dot is ink-coloured (this stage or earlier reached).
    *active* → dot is accent-coloured (the current stage).
    """
    if status in TERMINAL_STATUSES:
        return None
    active = _STATUS_STEP.get(status, 0)
    return [
        {
            "label": label,
            "filled": i <= active,
            "active": i == active,
        }
        for i, label in enumerate(STEPS)
    ]
