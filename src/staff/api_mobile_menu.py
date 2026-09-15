"""Staff mobile JSON for the Menu editor (Phase 6, the "Menu editor"
screen — docs/mobile/FLUTTER_APP_PLAN.md). Reshapes §12.7's dish
list/create/edit/archive flow (`staff/views.py::menu_list`/
`dish_create`/`dish_edit`/`dish_archive`/`dish_unarchive`) into JSON,
reusing the same forms (`staff/forms.py`'s `DishForm`/`DishOptionForm`/
`DishOptionValueForm`), the same `_enforce_single_featured_dish` /
`_dishes_with_occupying_orders` helpers, and the same
`storage.service.validate_dish_image`/`store_dish_image_bytes` calls the
web view uses for its image-upload branch — never a second copy of the
business logic. Options/values CRUD is genuinely new here (the web view
handles it via raw POST-key parsing inline in `dish_edit`; this module
gives each action its own small JSON endpoint per
`staff/urls_api_mobile.py`) but follows the exact same form/validation
rules.

Any staff role can reach every endpoint here (the "manager+" language in
`staff/views.py::menu_list`'s docstring is aspirational — no decorator
actually enforces even that on the web side either).
"""
from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.menu import dish_photo_url
from core.models import Dish, DishOption, DishOptionValue, Media, MediaKind
from core.tz import now_sast
from storage.service import (
    InvalidUpload,
    sha256_digest,
    store_dish_image_bytes,
    validate_dish_image,
)

from .api_mobile import _error_response, staff_login_required_json
from .forms import DishForm, DishOptionForm, DishOptionValueForm
from .views import _dishes_with_occupying_orders, _enforce_single_featured_dish


def _parse_json_body(request: HttpRequest) -> tuple[dict, JsonResponse | None]:
    """Same "Malformed JSON body." shape `api_mobile.login_json` and
    `api_mobile_daily_controls._post` already use, unified here as one
    helper since every mutating endpoint in this module needs it. An
    empty body (e.g. a plain `POST` with no JSON payload — `dish_archive_json`
    when the caller isn't sending `{"confirm": ...}`) parses to `{}`
    rather than erroring, since several endpoints here treat the whole
    body as optional.
    """
    raw = request.body.decode("utf-8") if request.body else "{}"
    try:
        data = json.loads(raw) if raw else {}
    except (ValueError, UnicodeDecodeError):
        return {}, _error_response("validation_error", "Malformed JSON body.")
    if not isinstance(data, dict):
        return {}, _error_response("validation_error", "Malformed JSON body.")
    return data, None


def _form_error_response(form) -> JsonResponse:
    fields = {name: "; ".join(str(e) for e in errs) for name, errs in form.errors.items()}
    message = "; ".join(
        f"{f}: {e}" for f, errs in form.errors.items() for e in errs
    ) or "Invalid data."
    return _error_response("validation_error", message, fields=fields)


def _upload_invalid_response(message: str, **extra: object) -> JsonResponse:
    """`upload_invalid` isn't in `api_mobile._ERROR_STATUS` (that dict is
    shared/off limits for this module to edit) — added locally, same 400
    every other upload-validation failure in this codebase uses
    (`InvalidUpload`'s own reasons: `type`, `size`, `corrupt`).
    """
    return JsonResponse({"error": "upload_invalid", "message": message, **extra}, status=400)


def _absolute_photo_url(request: HttpRequest, dish: Dish) -> str:
    """Same reasoning as `public/api.py::_absolute_photo_url` (see that
    function's own docstring, added 2026-09-15 after the Menu screen
    shipped zero dish cards): `core.menu.dish_photo_url()` returns a
    relative `/media/...` path in this deploy's current config, which a
    browser resolves fine but `Image.network()` cannot — always hand the
    Flutter app an absolute URL. `build_absolute_uri` is a no-op on an
    already-absolute URL (the CDN/S3 branches), so this is safe either way.
    """
    url = dish_photo_url(dish)
    return request.build_absolute_uri(url) if url else ""


# ---------------------------------------------------------------- read shapes


def _dish_list_row(dish: Dish, occupying: dict[int, int]) -> dict[str, object]:
    return {
        "id": dish.pk,
        "category": dish.category,
        "sort_order": dish.sort_order,
        "name": dish.name,
        "is_featured": dish.is_featured,
        "price_cents": dish.price_cents,
        "is_active_on_menu": dish.is_active_on_menu,
        "is_archived": dish.archived_at is not None,
        "occupying_order_count": occupying.get(dish.pk, 0),
    }


def _value_json(value: DishOptionValue) -> dict[str, object]:
    return {
        "id": value.pk,
        "name": value.name,
        "price_delta_cents": value.price_delta_cents,
        "sort_order": value.sort_order,
        "is_available": value.is_available,
    }


def _option_json(option: DishOption) -> dict[str, object]:
    return {
        "id": option.pk,
        "name": option.name,
        "required": option.required,
        "sort_order": option.sort_order,
        "values": [_value_json(v) for v in option.values.order_by("sort_order", "name")],
    }


def _dish_payload(dish: Dish, request: HttpRequest) -> dict[str, object]:
    """The edit-mode dish shape — deliberately excludes `slug` (immutable
    after create; `DishForm(editing=True)` drops the field from the form
    entirely for the same reason — see that form's own docstring).
    `dish_create_json`'s success response adds `slug` back in on top of
    this, since that response is the one place a freshly-assigned slug is
    worth showing.
    """
    occupying = _dishes_with_occupying_orders([dish.pk]).get(dish.pk, 0)
    return {
        "id": dish.pk,
        "name": dish.name,
        "price_cents": dish.price_cents,
        "portion_label": dish.portion_label,
        "short_description": dish.short_description,
        "long_description": dish.long_description,
        "spice_default": dish.spice_default,
        "allergen_text": dish.allergen_text,
        "dietary_tags": dish.dietary_tags,
        "category": dish.category,
        "sort_order": dish.sort_order,
        "is_active_on_menu": dish.is_active_on_menu,
        "allow_notes": dish.allow_notes,
        "is_featured": dish.is_featured,
        "is_archived": dish.archived_at is not None,
        "archived_at": dish.archived_at.isoformat() if dish.archived_at else None,
        "occupying_order_count": occupying,
        "photo_url": _absolute_photo_url(request, dish),
        "options": [
            _option_json(o)
            for o in dish.options.order_by("sort_order", "name").prefetch_related("values")
        ],
    }


# ---------------------------------------------------------------- list


@staff_login_required_json
@require_GET
def menu_list_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/menu/` — every dish including archived ones,
    same ordering as `staff.views.menu_list`.
    """
    dishes = list(Dish.objects.all().order_by("category", "sort_order", "name"))
    occupying = _dishes_with_occupying_orders([d.pk for d in dishes])
    return JsonResponse({"dishes": [_dish_list_row(d, occupying) for d in dishes]})


# ---------------------------------------------------------------- create


@staff_login_required_json
@require_http_methods(["GET", "POST"])
@csrf_protect
def dish_create_json(request: HttpRequest) -> JsonResponse:
    """`GET /api/v1/staff/menu/new/` — an empty-form scaffold (just the
    categories already in use, so the app can offer them as suggestions).
    `POST` creates a dish via `DishForm` (create mode — `slug` included)
    inside the same `transaction.atomic()` +
    `_enforce_single_featured_dish` dance `staff.views.dish_create` uses.
    """
    if request.method == "GET":
        categories = list(
            Dish.objects.exclude(category__isnull=True)
            .exclude(category="")
            .order_by("category")
            .values_list("category", flat=True)
            .distinct()
        )
        return JsonResponse({"categories": categories})

    data, err = _parse_json_body(request)
    if err:
        return err
    form = DishForm(data)
    if not form.is_valid():
        return _form_error_response(form)
    with transaction.atomic():
        dish = form.save()
        _enforce_single_featured_dish(dish)
    payload = _dish_payload(dish, request)
    payload["slug"] = dish.slug
    return JsonResponse({"dish": payload})


# ---------------------------------------------------------------- detail / edit


@staff_login_required_json
@require_http_methods(["GET", "POST"])
@csrf_protect
def dish_detail_json(request: HttpRequest, dish_id: int) -> JsonResponse:
    """`GET/POST /api/v1/staff/menu/<id>/` — full dish incl. options/
    values on `GET`; a plain field save (options/values/image/archive
    are their own endpoints below) on `POST`, via `DishForm(editing=True)`
    exactly like `staff.views.dish_edit`'s own plain-save branch.
    """
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        return _error_response("not_found", "Dish not found.")

    if request.method == "GET":
        return JsonResponse({"dish": _dish_payload(dish, request)})

    data, err = _parse_json_body(request)
    if err:
        return err
    form = DishForm(data, instance=dish, editing=True)
    if not form.is_valid():
        return _form_error_response(form)
    with transaction.atomic():
        form.save()
        _enforce_single_featured_dish(dish)
    return JsonResponse({"dish": _dish_payload(dish, request)})


# ---------------------------------------------------------------- image upload


@staff_login_required_json
@require_POST
@csrf_protect
def dish_image_upload_json(request: HttpRequest, dish_id: int) -> JsonResponse:
    """`POST /api/v1/staff/menu/<id>/image/` — multipart, field name
    `image` (matches `staff.views._handle_image_upload`'s own
    `request.FILES.get("image")`). Same validate/store calls that
    function uses; only the response shape differs (JSON, not a redirect
    + flash message).
    """
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        return _error_response("not_found", "Dish not found.")

    upload = request.FILES.get("image")
    if not upload:
        return _upload_invalid_response("No image provided.", reason="type")

    data = upload.read()
    try:
        mime_type = validate_dish_image(data)
    except InvalidUpload as exc:
        return _upload_invalid_response(str(exc), reason=exc.reason)

    storage_key = store_dish_image_bytes(data, mime_type)
    media = Media.objects.create(
        kind=MediaKind.DISH_IMAGE,
        storage_key=storage_key,
        mime_type=mime_type,
        byte_size=len(data),
        sha256=sha256_digest(data),
        dish=dish,
        uploaded_by=request.staff_user,
    )
    dish.image_media = media
    dish.save(update_fields=["image_media"])
    return JsonResponse({"photo_url": _absolute_photo_url(request, dish)})


# ---------------------------------------------------------------- archive / unarchive


@staff_login_required_json
@require_POST
@csrf_protect
def dish_archive_json(request: HttpRequest, dish_id: int) -> JsonResponse:
    """`POST /api/v1/staff/menu/<id>/archive/` — body `{"confirm": bool}`.
    D-25 soft delete: mirrors `staff.views.dish_archive` exactly —
    unconditional when the dish has no occupying orders, otherwise
    requires `confirm: true` or 400s with `affected_order_count` so the
    app can show the same confirm-gate the web editor does.
    """
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        return _error_response("not_found", "Dish not found.")

    data, err = _parse_json_body(request)
    if err:
        return err
    confirmed = data.get("confirm") is True

    occupying_orders = _dishes_with_occupying_orders([dish.pk]).get(dish.pk, 0)
    if occupying_orders and not confirmed:
        return _error_response(
            "validation_error",
            f"{dish.name} has {occupying_orders} occupying order(s). "
            "Confirm to archive it anyway — those orders keep their own snapshot.",
            affected_order_count=occupying_orders,
        )

    dish.archived_at = now_sast()
    dish.is_active_on_menu = False
    dish.save(update_fields=["archived_at", "is_active_on_menu"])
    return JsonResponse({"dish": _dish_payload(dish, request)})


@staff_login_required_json
@require_POST
@csrf_protect
def dish_unarchive_json(request: HttpRequest, dish_id: int) -> JsonResponse:
    """`POST /api/v1/staff/menu/<id>/unarchive/`. Note (same as the web,
    `staff.views.dish_unarchive`): does NOT restore `is_active_on_menu` —
    archiving forces that to `False` and unarchiving leaves it there. Not
    a bug to silently fix here; the staff member re-enables it themselves
    via a plain field save if they want it back on the menu.
    """
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        return _error_response("not_found", "Dish not found.")
    dish.archived_at = None
    dish.save(update_fields=["archived_at"])
    return JsonResponse({"dish": _dish_payload(dish, request)})


# ---------------------------------------------------------------- options


@staff_login_required_json
@require_POST
@csrf_protect
def dish_option_create_json(request: HttpRequest, dish_id: int) -> JsonResponse:
    """`POST /api/v1/staff/menu/<id>/options/` — add an option
    (`DishOptionForm`: name/required/sort_order)."""
    dish = Dish.objects.filter(pk=dish_id).first()
    if dish is None:
        return _error_response("not_found", "Dish not found.")

    data, err = _parse_json_body(request)
    if err:
        return err
    form = DishOptionForm(data)
    if not form.is_valid():
        return _form_error_response(form)
    option = form.save(commit=False)
    option.dish = dish
    option.save()
    return JsonResponse({"option": _option_json(option)})


@staff_login_required_json
@require_http_methods(["POST", "DELETE"])
@csrf_protect
def dish_option_detail_json(request: HttpRequest, dish_id: int, option_id: int) -> JsonResponse:
    """`POST` edits an option (full `DishOptionForm` resave — send every
    field, same as any other edit form here); `DELETE` removes it. Values
    cascade-delete with it (`DishOptionValue.option`'s FK is
    `on_delete=models.CASCADE` — verified in `core/models.py`), so no
    manual cleanup is needed here.
    """
    option = DishOption.objects.filter(pk=option_id, dish_id=dish_id).first()
    if option is None:
        return _error_response("not_found", "Option not found.")

    if request.method == "DELETE":
        option.delete()
        return JsonResponse({"ok": True})

    data, err = _parse_json_body(request)
    if err:
        return err
    form = DishOptionForm(data, instance=option)
    if not form.is_valid():
        return _form_error_response(form)
    form.save()
    return JsonResponse({"option": _option_json(option)})


# ---------------------------------------------------------------- option values


@staff_login_required_json
@require_POST
@csrf_protect
def dish_option_value_create_json(
    request: HttpRequest, dish_id: int, option_id: int
) -> JsonResponse:
    """`POST /api/v1/staff/menu/<id>/options/<id>/values/` — add a value
    (`DishOptionValueForm`: name/price_delta_cents/sort_order/
    is_available). Same nuance `staff.views.dish_edit`'s `add_value`
    branch documents: the inline add-value form has no availability
    input, so an absent `is_available` key must not silently override the
    model's own `is_available=True` default with `False`.
    """
    option = DishOption.objects.filter(pk=option_id, dish_id=dish_id).first()
    if option is None:
        return _error_response("not_found", "Option not found.")

    data, err = _parse_json_body(request)
    if err:
        return err
    if "is_available" not in data:
        data["is_available"] = True
    form = DishOptionValueForm(data)
    if not form.is_valid():
        return _form_error_response(form)
    value = form.save(commit=False)
    value.option = option
    value.save()
    return JsonResponse({"value": _value_json(value)})


@staff_login_required_json
@require_http_methods(["POST", "DELETE"])
@csrf_protect
def dish_option_value_detail_json(
    request: HttpRequest, dish_id: int, option_id: int, value_id: int
) -> JsonResponse:
    """`POST` edits a value, including toggling `is_available` — a full
    `DishOptionValueForm` resave (send every field: `name`,
    `price_delta_cents`, `sort_order`, `is_available`), same as
    `dish_option_detail_json`'s edit branch and every other edit form in
    this module. `DELETE` removes it.
    """
    value = DishOptionValue.objects.filter(
        pk=value_id, option_id=option_id, option__dish_id=dish_id,
    ).first()
    if value is None:
        return _error_response("not_found", "Value not found.")

    if request.method == "DELETE":
        value.delete()
        return JsonResponse({"ok": True})

    data, err = _parse_json_body(request)
    if err:
        return err
    form = DishOptionValueForm(data, instance=value)
    if not form.is_valid():
        return _form_error_response(form)
    form.save()
    return JsonResponse({"value": _value_json(value)})
