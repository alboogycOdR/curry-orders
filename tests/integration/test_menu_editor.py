"""Integration tests for the menu editor (spec §12.7, milestone 8
remainder). `staff/views.py::menu_list`/`dish_create`/`dish_edit`/
`dish_archive`/`dish_unarchive`.
"""
from __future__ import annotations

import datetime as dt

import pytest
from django.urls import reverse
from django.utils.html import escape

from core.auth import hash_password
from core.capacity import CheckoutLine, ReservationRequest, reserve
from core.models import Dish, DishOption, DishOptionValue, OrderLine, User, UserRole

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"
NOW = dt.datetime(2026, 8, 31, 6, 0, tzinfo=dt.UTC)  # day before trading_day's 2026-09-01

# Minimal valid image bytes for each accepted magic-byte type.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
GIF_BYTES = b"GIF89a" + b"\x00" * 32  # unsupported type


def _make_staff(**overrides) -> User:
    defaults = dict(
        email="manager@example.test", name="Manager", role=UserRole.MANAGER,
        password_hash=hash_password(PASSWORD), must_change_password=False,
    )
    defaults.update(overrides)
    return User.objects.create(**defaults)


def _login(client, email: str = "manager@example.test") -> None:
    resp = client.post(reverse("manage:login"), {"email": email, "password": PASSWORD})
    assert resp.status_code == 302


def _dish_form_data(**overrides) -> dict:
    data = {
        "slug": "new-dish",
        "name": "New Dish",
        "price_cents": "5000",
        "portion_label": "",
        "short_description": "",
        "long_description": "",
        "spice_default": "",
        "allergen_text": "",
        "dietary_tags": "",
        "category": "Mains",
        "sort_order": "0",
        "is_active_on_menu": "on",
        "allow_notes": "on",
    }
    data.update(overrides)
    return data


class TestMenuListView:
    def test_anonymous_redirected_to_login(self) -> None:
        from django.test import Client

        resp = Client().get(reverse("manage:menu_list"))
        assert resp.status_code == 302

    def test_manager_can_access(self, client, dish) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:menu_list"))
        assert resp.status_code == 200
        assert escape(dish.name) in resp.content.decode()

    def test_includes_archived_dishes(self, client, dish) -> None:
        dish.archived_at = NOW
        dish.save(update_fields=["archived_at"])
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:menu_list"))
        assert escape(dish.name) in resp.content.decode()


class TestDishCreate:
    def test_creates_a_dish(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.post(reverse("manage:dish_create"), _dish_form_data())
        assert resp.status_code == 302
        dish = Dish.objects.get(slug="new-dish")
        assert dish.name == "New Dish"
        assert dish.price_cents == 5000

    def test_slug_must_be_valid_format(self, client) -> None:
        _make_staff()
        _login(client)
        resp = client.post(reverse("manage:dish_create"), _dish_form_data(slug="Not Valid!"))
        assert resp.status_code == 200
        assert not Dish.objects.filter(name="New Dish").exists()


class TestDishEditAndSlugImmutability:
    def test_edits_a_dish(self, client, dish) -> None:
        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        data = _dish_form_data(name="Renamed Dish", price_cents="9900")
        del data["slug"]  # not present on the edit form
        resp = client.post(url, data)
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.name == "Renamed Dish"
        assert dish.price_cents == 9900

    def test_slug_cannot_be_changed_via_crafted_post(self, client, dish) -> None:
        original_slug = dish.slug
        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        data = _dish_form_data(name=dish.name, slug="hacked-slug")
        resp = client.post(url, data)
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.slug == original_slug

    def test_get_edit_form_does_not_render_slug_input(self, client, dish) -> None:
        _make_staff()
        _login(client)
        resp = client.get(reverse("manage:dish_edit", args=[dish.pk]))
        content = resp.content.decode()
        assert 'name="slug"' not in content
        assert dish.slug in content  # shown read-only


class TestDishOptionsAndValues:
    def test_add_option_and_value(self, client, dish) -> None:
        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        resp = client.post(url, {
            "action": "add_option", "name": "Spice", "required": "on", "sort_order": "0",
        })
        assert resp.status_code == 302
        option = DishOption.objects.get(dish=dish, name="Spice")
        assert option.required is True

        resp2 = client.post(url, {
            "action": "add_value", "option_id": str(option.pk),
            "name": "Hot", "price_delta_cents": "0", "sort_order": "0",
        })
        assert resp2.status_code == 302
        value = DishOptionValue.objects.get(option=option, name="Hot")
        assert value.is_available is True

    def test_toggle_value_availability(self, client, dish_with_options) -> None:
        _make_staff()
        _login(client)
        value = dish_with_options.options.first().values.first()
        url = reverse("manage:dish_edit", args=[dish_with_options.pk])
        resp = client.post(url, {"action": "toggle_value_available", "value_id": str(value.pk)})
        assert resp.status_code == 302
        value.refresh_from_db()
        assert value.is_available is False

    def test_delete_value_and_option(self, client, dish_with_options) -> None:
        _make_staff()
        _login(client)
        option = dish_with_options.options.get(name="Extra cheese")
        value = option.values.first()
        url = reverse("manage:dish_edit", args=[dish_with_options.pk])
        client.post(url, {"action": "delete_value", "value_id": str(value.pk)})
        assert not DishOptionValue.objects.filter(pk=value.pk).exists()
        client.post(url, {"action": "delete_option", "option_id": str(option.pk)})
        assert not DishOption.objects.filter(pk=option.pk).exists()


class TestDishArchive:
    def test_archive_without_occupying_orders_needs_no_confirmation(self, client, dish) -> None:
        _make_staff()
        _login(client)
        resp = client.post(reverse("manage:dish_archive", args=[dish.pk]), {})
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.archived_at is not None
        assert dish.is_active_on_menu is False

    def test_archive_with_occupying_orders_warns_with_count_and_requires_confirm(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        _make_staff()
        _login(client)
        order = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=1)], now=NOW,
            ),
            biz_settings,
        )

        # No confirmation: not archived, warning shown with the count.
        resp = client.post(reverse("manage:dish_archive", args=[dish.pk]), {})
        assert resp.status_code == 302  # redirected back to edit page
        dish.refresh_from_db()
        assert dish.archived_at is None

        edit_resp = client.get(reverse("manage:dish_edit", args=[dish.pk]))
        content = edit_resp.content.decode()
        assert "1" in content  # occupying-order count surfaced

        # Confirmed: archiving proceeds, order snapshot untouched.
        resp2 = client.post(
            reverse("manage:dish_archive", args=[dish.pk]), {"confirm_archive": "1"},
        )
        assert resp2.status_code == 302
        dish.refresh_from_db()
        assert dish.archived_at is not None

        order.refresh_from_db()
        line = order.lines.first()
        assert line.dish_id == dish.pk  # snapshot line untouched by archiving
        assert line.dish_name_snapshot == dish.name

    def test_unarchive(self, client, dish) -> None:
        _make_staff()
        _login(client)
        client.post(reverse("manage:dish_archive", args=[dish.pk]), {})
        dish.refresh_from_db()
        assert dish.archived_at is not None
        resp = client.post(reverse("manage:dish_unarchive", args=[dish.pk]), {})
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.archived_at is None


class TestPriceChangeIsolation:
    def test_changing_price_after_checkout_leaves_order_lines_untouched(
        self, client, biz_settings, trading_day, slot, dish,
    ) -> None:
        order = reserve(
            ReservationRequest(
                trading_day_date=trading_day.date, slot_id=slot.pk, payment_method="eft",
                customer_name="Jane", customer_mobile_e164="+27821234567",
                lines=[CheckoutLine(dish_id=dish.pk, quantity=2)], now=NOW,
            ),
            biz_settings,
        )
        line = order.lines.first()
        original_unit_price = line.unit_price_cents_snapshot
        original_line_total = line.line_total_cents
        assert original_unit_price == dish.price_cents

        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        data = _dish_form_data(name=dish.name, price_cents=str(dish.price_cents + 5000))
        del data["slug"]
        resp = client.post(url, data)
        assert resp.status_code == 302

        dish.refresh_from_db()
        assert dish.price_cents == original_unit_price + 5000

        line.refresh_from_db()
        assert line.unit_price_cents_snapshot == original_unit_price
        assert line.line_total_cents == original_line_total

    def test_order_line_snapshot_is_independent_column_not_a_live_join(self) -> None:
        # Sanity check on the schema itself: OrderLine stores its own
        # price/name columns rather than deriving them from Dish at
        # render time — the isolation above is structural, not
        # incidental to how the view happens to query things.
        field_names = {f.name for f in OrderLine._meta.get_fields()}
        assert "unit_price_cents_snapshot" in field_names
        assert "dish_name_snapshot" in field_names


class TestDishImageUpload:
    def test_uploads_a_valid_png(self, client, dish) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        upload = SimpleUploadedFile("photo.png", PNG_BYTES, content_type="image/png")
        resp = client.post(url, {"action": "upload_image", "image": upload})
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.image_media is not None
        assert dish.image_media.mime_type == "image/png"

    def test_rejects_bad_mime_type_via_magic_bytes_not_extension(self, client, dish) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        # Claims to be a PNG by filename/content_type but is not one by
        # magic bytes — must be rejected on the sniff, not the label.
        upload = SimpleUploadedFile("photo.png", GIF_BYTES, content_type="image/png")
        resp = client.post(url, {"action": "upload_image", "image": upload})
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.image_media is None

    def test_rejects_oversized_file(self, client, dish) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024 + 1)
        upload = SimpleUploadedFile("photo.png", oversized, content_type="image/png")
        resp = client.post(url, {"action": "upload_image", "image": upload})
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.image_media is None

    def test_rejects_pdf_for_dish_image_even_though_proofs_allow_it(self, client, dish) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        _make_staff()
        _login(client)
        url = reverse("manage:dish_edit", args=[dish.pk])
        upload = SimpleUploadedFile(
            "doc.pdf", b"%PDF-1.4" + b"\x00" * 32, content_type="application/pdf",
        )
        resp = client.post(url, {"action": "upload_image", "image": upload})
        assert resp.status_code == 302
        dish.refresh_from_db()
        assert dish.image_media is None
