"""Menu/dish/availability queries (spec §7.3-§7.7, milestone 2). Pure
read-side: no HTTP imports (§17.2), and no capacity *reservation* — just
"what's on the menu for this date, and is it sold out". Order-level
consumption (`core.capacity.dish_units_used`) is folded in here too,
since §7.7's own availability rule is silent on live consumption but
§8.2 ceiling 3 (`dish_qty_exceeded`) makes clear that a `max_units` cap is
about *remaining* units, not just the static flag — showing a dish as
orderable here when checkout would immediately reject it would be a
worse customer experience than the extra query costs.
"""
from __future__ import annotations

from dataclasses import dataclass

from storage.service import public_dish_image_url

from .capacity import dish_units_used
from .models import DayDishAvailability, Dish, TradingDay


@dataclass(frozen=True)
class MenuDishOptionValue:
    id: int
    name: str
    price_delta_cents: int
    is_available: bool


@dataclass(frozen=True)
class MenuDishOption:
    id: int
    name: str
    required: bool
    values: list[MenuDishOptionValue]


@dataclass(frozen=True)
class MenuDish:
    id: int
    slug: str
    name: str
    short_description: str
    price_cents: int
    portion_label: str
    dietary_tags: list[str]
    category: str
    sold_out: bool
    options: list[MenuDishOption]
    photo_url: str = ""


def dish_photo_url(dish: Dish) -> str:
    media = getattr(dish, "image_media", None)
    if media is None or not getattr(media, "storage_key", None):
        return ""
    return public_dish_image_url(media.storage_key)


def active_dishes() -> list[Dish]:
    """Every dish visible on the monthly menu at all (§7.3:
    `is_active_on_menu` is the monthly switch; `archived_at` is D-25's
    soft delete) — independent of any one day's availability.
    """
    return list(
        Dish.objects.filter(is_active_on_menu=True, archived_at__isnull=True)
        .select_related("image_media")
        .order_by("category", "sort_order", "name")
    )


def dishes_for_date(trading_day: TradingDay, *, with_options: bool = False) -> list[MenuDish]:
    """§7.3-§7.7's menu-page read: every active dish, each flagged
    `sold_out` for this specific date. §7.7: "Absent row ⇒ available if
    `dishes.is_active_on_menu AND archived_at IS NULL`, uncapped" — so a
    dish with no `DayDishAvailability` row for this day is simply never
    sold out here; one with `is_available=False` or a reached
    `max_units` is.
    """
    dishes = active_dishes()
    dish_ids = [d.pk for d in dishes]
    avail_rows = {
        row.dish_id: row
        for row in DayDishAvailability.objects.filter(trading_day=trading_day, dish_id__in=dish_ids)
    }
    used = dish_units_used(trading_day, dish_ids)

    result = []
    for dish in dishes:
        avail = avail_rows.get(dish.pk)
        sold_out = False
        if avail is not None:
            if not avail.is_available:
                sold_out = True
            elif avail.max_units is not None and used.get(dish.pk, 0) >= avail.max_units:
                sold_out = True

        options = dish_options(dish) if with_options else []
        result.append(MenuDish(
            id=dish.pk,
            slug=dish.slug,
            name=dish.name,
            short_description=dish.short_description or "",
            price_cents=dish.price_cents,
            portion_label=dish.portion_label or "",
            dietary_tags=dish.dietary_tags,
            category=dish.category or "",
            sold_out=sold_out,
            options=options,
            photo_url=dish_photo_url(dish),
        ))
    return result


def dish_options(dish: Dish) -> list[MenuDishOption]:
    options = []
    for option in dish.options.order_by("sort_order", "name"):
        values = [
            MenuDishOptionValue(v.pk, v.name, v.price_delta_cents, v.is_available)
            for v in option.values.order_by("sort_order", "name")
        ]
        options.append(MenuDishOption(option.pk, option.name, option.required, values))
    return options


def dish_by_slug(slug: str) -> Dish | None:
    """§7.3: `slug` is immutable/permalink-stable — a dish page still
    resolves after the dish is archived (so old links don't 404 outright
    — spec doesn't say to hide archived dishes from `/dishes/:slug`
    itself, only from the menu listing), the *caller* decides what to
    show for an archived one.
    """
    return Dish.objects.filter(slug=slug).first()


def categories_ordered(dishes: list[MenuDish]) -> list[tuple[str, list[MenuDish]]]:
    """Group an already-fetched, already-ordered dish list by
    `category`, preserving first-appearance order — used to render menu
    sections without a second query. Plate-letter labelling (A, B, C...)
    is presentational only (the handoff's own device, §2 "Order"); it is
    not stored anywhere and is assigned here purely by group order.
    """
    grouped: dict[str, list[MenuDish]] = {}
    for dish in dishes:
        grouped.setdefault(dish.category, []).append(dish)
    return list(grouped.items())
