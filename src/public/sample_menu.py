"""Sample menu content for the four Broadsheet screen templates.

This is placeholder copy, not the real menu — spec §23 lists "Final dish
list: name, price, portion, options, allergen text, dietary tags, photos"
as an **Outstanding** owner input, and `core.Dish` (the real table) has no
rows yet. The design handoff (`updates/.../design_handoff_brandons_kitchen/
README.md` §2 "Order") is explicit that this exact content — names,
descriptions, prices — is "copy to keep verbatim" for the visual pass, so
it's transcribed here unchanged from the handoff's own `MENU` JS array
rather than invented fresh.

One dict, used from three places, so the served-priced content is never
duplicated by hand:
  - `public.views.order` passes it to order.html, which server-renders the
    menu listing AND json_script's it for order.js (the cart engine needs
    the same id -> {name, price} map client-side to price the cart and
    render the order sheet without a round-trip).
  - `public.views.checkout` json_script's it again so checkout.js can
    re-render the order sheet/total from the cart alone (the customer may
    land on /checkout/ without /order/ having just rendered in the same
    request).
  - `public.views.home` picks three fixed dishes out of it for "Today's
    picks".

Replace this module wholesale with real `core.Dish`/`core.DishOptionValue`
queries in milestone 2 (spec §22 row 2) — nothing downstream should need
to change shape-wise: `as_cart_items()` is the one function that matters
to callers.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dish:
    id: str
    name: str
    desc: str
    price: int  # rand, integer per the handoff's sample prices
    note: str = ""


@dataclass(frozen=True)
class Category:
    letter: str
    name: str
    portion: str
    dishes: tuple[Dish, ...]


MENU: tuple[Category, ...] = (
    Category(
        letter="A",
        name="Roti & Curry",
        portion="Serves 1",
        dishes=(
            Dish("cc", "Chicken Curry & Roti",
                 "Slow-simmered chicken curry, mopped up with a soft roti.", 85),
            Dish("sc", "Steak Curry & Roti",
                 "Beef steak curry, rich and slow-cooked, served with roti.", 95),
        ),
    ),
    Category(
        letter="A3",
        name="Masala Roti Rolls",
        portion="Serves 1",
        dishes=(
            Dish("crr", "Chicken Masala Roti Roll",
                 "Chips, masala chicken and roti, rolled tight.", 65),
            Dish("srr", "Steak Masala Roti Roll",
                 "Chips, masala steak and roti, rolled tight.", 70),
        ),
    ),
    Category(
        letter="B",
        name="Roti & Gatsby, Large",
        portion="Serves 4",
        dishes=(
            Dish("cgr", "Chicken Masala Roti & Gatsby",
                 "A large gatsby loaded with masala chicken, plus roti on the side.", 110),
            Dish("sgr", "Masala Steak Roti & Gatsby",
                 "A large gatsby loaded with masala steak, plus roti on the side.", 115),
        ),
    ),
    Category(
        letter="C",
        name="Gatsby",
        portion="Serves 4",
        dishes=(
            Dish("cg", "Chicken Masala Gatsby",
                 "The Cape classic — masala chicken, chips and all the trimmings in a "
                 "full loaf.", 95),
            Dish("sg", "Steak Masala Gatsby",
                 "Masala steak, chips and all the trimmings in a full loaf.", 100),
            Dish("fh", "Full House Masala Steak Gatsby",
                 "Masala steak loaded with egg and cheese. The full house, no shortcuts.",
                 130, note="Portion to confirm"),
        ),
    ),
    Category(
        letter="D",
        name="Italian Lasagne",
        portion="Serves 1",
        dishes=(
            Dish("bl", "Beef Lasagne", "Layered beef lasagne, baked to order.", 90),
        ),
    ),
)


def as_context() -> list[dict]:
    """Server-render shape for order.html's `{% for %}` menu listing."""
    return [
        {
            "letter": cat.letter,
            "name": cat.name,
            "portion": cat.portion,
            "dishes": [
                {"id": d.id, "name": d.name, "desc": d.desc, "price": d.price, "note": d.note}
                for d in cat.dishes
            ],
        }
        for cat in MENU
    ]


def as_price_map() -> dict:
    """id -> {name, price}, the shape order.js/checkout.js need to price a
    cart and render an order sheet client-side without a round-trip. Passed
    into both templates via `{{ menu_price_map|json_script:"menu-data" }}`.
    """
    return {d.id: {"name": d.name, "price": d.price} for cat in MENU for d in cat.dishes}


def dish_by_id(dish_id: str) -> Dish | None:
    for cat in MENU:
        for d in cat.dishes:
            if d.id == dish_id:
                return d
    return None
