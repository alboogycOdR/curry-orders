"""South African mobile number normalisation and validation (spec §11.6
checkout field table, §18 edge case 18).

Accepts `082...`, `+2782...`, `2782...`, `0027...` and normalises all of
them to E.164 `+27...`, matching `customers.mobile_e164` /
`orders.customer_mobile_snapshot`'s DB CHECK in schema_v1_1.sql:
`^\\+27[6-8][0-9]{8}$` — i.e. a South African *mobile* number (leading
national digit 6, 7 or 8 after the 27); landlines and other prefixes are
rejected.
"""
from __future__ import annotations

import re

E164_SA_MOBILE_RE = re.compile(r"^\+27[6-8]\d{8}$")


class InvalidPhoneNumber(ValueError):
    """Raised when a value cannot be normalised to a valid SA E.164 mobile."""


def normalize_sa_mobile(raw: str) -> str:
    """Normalise `raw` to E.164 (`+27XXXXXXXXX`).

    Accepted input shapes (spec §11.6): `082...`, `+2782...`, `2782...`,
    `0027...` — with or without spaces/hyphens. Raises
    `InvalidPhoneNumber` for anything that does not resolve to a valid SA
    mobile number (wrong length, or a national prefix other than 6/7/8,
    e.g. a landline).
    """
    if not raw or not raw.strip():
        raise InvalidPhoneNumber("empty phone number")

    cleaned = re.sub(r"[\s\-()]", "", raw.strip())

    if cleaned.startswith("+27"):
        national = cleaned[3:]
    elif cleaned.startswith("0027"):
        national = cleaned[4:]
    elif cleaned.startswith("27") and len(cleaned) == 11:
        national = cleaned[2:]
    elif cleaned.startswith("0"):
        national = cleaned[1:]
    else:
        national = cleaned

    if not national.isdigit() or len(national) != 9:
        raise InvalidPhoneNumber(f"not a valid SA mobile number: {raw!r}")

    candidate = f"+27{national}"
    if not E164_SA_MOBILE_RE.match(candidate):
        raise InvalidPhoneNumber(f"not a valid SA mobile number: {raw!r}")
    return candidate


def is_valid_sa_mobile(value: str) -> bool:
    """True iff `value` is already a normalised E.164 SA mobile number."""
    return bool(E164_SA_MOBILE_RE.match(value))
