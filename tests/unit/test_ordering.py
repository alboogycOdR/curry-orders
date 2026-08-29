"""Unit tests for core/ordering.py — order numbers, option_key, and line
pricing (spec §8.3, D-29). All pure functions, no database.
"""
from __future__ import annotations

from datetime import date

from core.ordering import derive_option_key, format_order_number, generate_public_token, price_line


class TestFormatOrderNumber:
    def test_matches_orders_order_number_check_constraint_shape(self) -> None:
        # orders_order_number_format: ^CT-[0-9]{6}-[0-9]{4}$
        number = format_order_number(date(2026, 9, 5), 7)
        assert number == "CT-260905-0007"
        import re
        assert re.match(r"^CT-[0-9]{6}-[0-9]{4}$", number)

    def test_seq_is_zero_padded_to_four_digits(self) -> None:
        assert format_order_number(date(2026, 1, 1), 1) == "CT-260101-0001"

    def test_seq_at_the_spec_max_still_fits(self) -> None:
        # trading_days_next_order_seq_range CHECK allows up to 10000.
        assert format_order_number(date(2026, 1, 1), 9999) == "CT-260101-9999"


class TestGeneratePublicToken:
    def test_length_clears_the_min_length_check_with_margin(self) -> None:
        # orders_public_token_min_length: ^.{22,}$
        token = generate_public_token()
        assert len(token) >= 22

    def test_url_safe_and_unique_across_calls(self) -> None:
        tokens = {generate_public_token() for _ in range(50)}
        assert len(tokens) == 50
        for t in tokens:
            assert all(c.isalnum() or c in "-_" for c in t)


class TestDeriveOptionKey:
    def test_empty_selections_gives_empty_string(self) -> None:
        assert derive_option_key([]) == ""

    def test_single_selection(self) -> None:
        assert derive_option_key([("Spice", "Mild")]) == "Spice=Mild"

    def test_sorted_by_option_name_regardless_of_input_order(self) -> None:
        a = derive_option_key([("Starch", "Rice"), ("Spice", "Mild")])
        b = derive_option_key([("Spice", "Mild"), ("Starch", "Rice")])
        assert a == b == "Spice=Mild|Starch=Rice"


class TestPriceLine:
    def test_no_options(self) -> None:
        pricing = price_line(8500, [], 2)
        assert pricing.unit_price_cents == 8500
        assert pricing.line_total_cents == 17000

    def test_option_deltas_add_to_unit_price(self) -> None:
        pricing = price_line(13000, [0, 1500], 1)
        assert pricing.unit_price_cents == 14500
        assert pricing.line_total_cents == 14500

    def test_quantity_multiplies_the_full_unit_price_including_deltas(self) -> None:
        pricing = price_line(10000, [500], 3)
        assert pricing.unit_price_cents == 10500
        assert pricing.line_total_cents == 31500
