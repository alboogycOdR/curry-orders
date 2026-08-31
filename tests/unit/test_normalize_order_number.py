"""Unit tests for ``core.lookup.normalize_order_number`` (Task 7, PR 7).

The function must canonicalize all recognisable ``CT-YYMMDD-NNNN`` variants
(dashes optional, any case) to the canonical form, and pass everything else
through as upper-cased only.
"""
from core.lookup import normalize_order_number


def test_canonical_form_unchanged() -> None:
    assert normalize_order_number("CT-260901-0001") == "CT-260901-0001"


def test_lowercase_canonicalized() -> None:
    assert normalize_order_number("ct-260901-0001") == "CT-260901-0001"


def test_mixed_case_canonicalized() -> None:
    assert normalize_order_number("Ct-260901-0001") == "CT-260901-0001"


def test_missing_first_dash_canonicalized() -> None:
    assert normalize_order_number("CT260901-0001") == "CT-260901-0001"


def test_missing_second_dash_canonicalized() -> None:
    assert normalize_order_number("CT-2609010001") == "CT-260901-0001"


def test_both_dashes_missing_canonicalized() -> None:
    assert normalize_order_number("CT2609010001") == "CT-260901-0001"


def test_whitespace_stripped() -> None:
    assert normalize_order_number("  CT-260901-0001  ") == "CT-260901-0001"


def test_rc_number_uppercased_not_canonicalized() -> None:
    # RC- numbers are not valid — passed through upper-cased; find_order
    # returns None since no order has that number format (D-01/spec §11.10).
    assert normalize_order_number("rc-1847") == "RC-1847"


def test_garbage_uppercased() -> None:
    assert normalize_order_number("not-an-order") == "NOT-AN-ORDER"
