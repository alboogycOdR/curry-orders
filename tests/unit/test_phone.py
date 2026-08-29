"""Unit tests for core/phone.py — spec §11.6 / §18 edge case 18 / §20.5."""
from __future__ import annotations

import pytest

from core.phone import InvalidPhoneNumber, is_valid_sa_mobile, normalize_sa_mobile

VALID_NATIONAL = "821234567"  # 9 digits, leading 8 -> valid mobile prefix
EXPECTED_E164 = "+27821234567"


class TestNormalizeAcceptedFormats:
    @pytest.mark.parametrize(
        "raw",
        [
            "0821234567",  # 082...
            "+27821234567",  # +2782...
            "27821234567",  # 2782...
            "0027821234567",  # 0027...
            "082 123 4567",  # spaces
            "082-123-4567",  # hyphens
            " 0821234567 ",  # surrounding whitespace
        ],
    )
    def test_normalises_to_e164(self, raw: str) -> None:
        assert normalize_sa_mobile(raw) == EXPECTED_E164

    @pytest.mark.parametrize("leading_digit", ["6", "7", "8"])
    def test_all_mobile_prefixes_accepted(self, leading_digit: str) -> None:
        raw = f"0{leading_digit}01234567"
        result = normalize_sa_mobile(raw)
        assert result.startswith(f"+27{leading_digit}")
        assert is_valid_sa_mobile(result)


class TestNormalizeRejectsInvalid:
    def test_empty_string_rejected(self) -> None:
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile("")

    def test_none_rejected(self) -> None:
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile(None)  # type: ignore[arg-type]

    def test_landline_prefix_rejected(self) -> None:
        # 021... is a Cape Town landline, not a mobile number.
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile("0211234567")

    def test_leading_5_rejected_not_a_mobile_prefix(self) -> None:
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile("0501234567")

    def test_too_short_rejected(self) -> None:
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile("08212345")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile("082123456789")

    def test_non_numeric_rejected(self) -> None:
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile("082abc4567")

    def test_wrong_country_code_rejected(self) -> None:
        with pytest.raises(InvalidPhoneNumber):
            normalize_sa_mobile("+1821234567")


class TestIsValidSaMobile:
    def test_valid_e164(self) -> None:
        assert is_valid_sa_mobile("+27821234567") is True

    def test_invalid_missing_plus(self) -> None:
        assert is_valid_sa_mobile("27821234567") is False

    def test_invalid_landline(self) -> None:
        assert is_valid_sa_mobile("+27211234567") is False
