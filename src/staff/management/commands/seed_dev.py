"""`manage.py seed_dev` — local-development-only bootstrap.

Spec §21 names two seed commands: `seed_pilot` ("settings with §3
defaults and owner-supplied values from §23; 1 owner + 2 manager users
... monthly dish catalogue from the owner's list; trading days
today+10 open") for the real pilot, and `seed_dev` ("placeholder dishes
and sample orders for local development only"). `seed_pilot` needs real
owner input that spec §23 still lists as Outstanding (bank details, the
*real* dish list, ...) — not buildable yet. This is the `seed_dev` half
spec already named: a settings row, staff accounts to log in with, a
materialised trading calendar, and now (milestone 2) a placeholder dish
catalogue — the same content the design handoff's own sample menu used
(`updates/.../design_handoff_brandons_kitchen/README.md` §2 "Order"),
migrated from hard-coded template content into real `core.Dish` rows now
that the public menu/dish pages read the database instead of a Python
module. Sample orders (the rest of what `seed_dev` is eventually for)
land once `core.capacity.reserve()` has a real caller to seed against
(milestone 3).

**Never run this against a production database** — it creates staff
accounts with printed temporary passwords. Nothing here checks
`DEBUG`/environment because the owner-facing `seed_pilot` command is the
intended prod path once it exists; this one stays a plain human judgement
call same as any other `manage.py` command, documented instead of gated.
"""
from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from core.auth import hash_password
from core.materialise import materialise_days
from core.models import Dish, DishOption, DishOptionValue, Settings, User, UserRole
from core.tz import now_sast

_DEV_STAFF = [
    ("owner@example.test", "Dev Owner", UserRole.OWNER),
    ("manager1@example.test", "Dev Manager One", UserRole.MANAGER),
    ("manager2@example.test", "Dev Manager Two", UserRole.MANAGER),
]

# Copy kept verbatim from the design handoff's own sample MENU (README §2)
# — placeholder pending the real dish list (spec §23, still Outstanding).
# `options` is `[(option_name, required, [(value_name, delta_cents), ...])]`.
_DEV_DISHES = [
    {"category": "Roti & Curry", "slug": "chicken-curry-roti", "name": "Chicken Curry & Roti",
     "desc": "Slow-simmered chicken curry, mopped up with a soft roti.", "price": 8500,
     "portion": "Serves 1"},
    {"category": "Roti & Curry", "slug": "steak-curry-roti", "name": "Steak Curry & Roti",
     "desc": "Beef steak curry, rich and slow-cooked, served with roti.", "price": 9500,
     "portion": "Serves 1"},
    {"category": "Masala Roti Rolls", "slug": "chicken-masala-roti-roll",
     "name": "Chicken Masala Roti Roll", "desc": "Chips, masala chicken and roti, rolled tight.",
     "price": 6500, "portion": "Serves 1"},
    {"category": "Masala Roti Rolls", "slug": "steak-masala-roti-roll",
     "name": "Steak Masala Roti Roll", "desc": "Chips, masala steak and roti, rolled tight.",
     "price": 7000, "portion": "Serves 1"},
    {"category": "Roti & Gatsby, Large", "slug": "chicken-masala-roti-gatsby",
     "name": "Chicken Masala Roti & Gatsby",
     "desc": "A large gatsby loaded with masala chicken, plus roti on the side.",
     "price": 11000, "portion": "Serves 4"},
    {"category": "Roti & Gatsby, Large", "slug": "masala-steak-roti-gatsby",
     "name": "Masala Steak Roti & Gatsby",
     "desc": "A large gatsby loaded with masala steak, plus roti on the side.",
     "price": 11500, "portion": "Serves 4"},
    {"category": "Gatsby", "slug": "chicken-masala-gatsby", "name": "Chicken Masala Gatsby",
     "desc": "The Cape classic — masala chicken, chips and all the trimmings in a full loaf.",
     "price": 9500, "portion": "Serves 4"},
    {"category": "Gatsby", "slug": "steak-masala-gatsby", "name": "Steak Masala Gatsby",
     "desc": "Masala steak, chips and all the trimmings in a full loaf.",
     "price": 10000, "portion": "Serves 4"},
    {"category": "Gatsby", "slug": "full-house-masala-steak-gatsby",
     "name": "Full House Masala Steak Gatsby",
     "desc": "Masala steak loaded with egg and cheese. The full house, no shortcuts.",
     "price": 13000, "portion": "Serves 4 — portion to confirm",
     "options": [("Spice", True, [("Mild", 0), ("Medium", 0), ("Hot", 0)])]},
    {"category": "Italian Lasagne", "slug": "beef-lasagne", "name": "Beef Lasagne",
     "desc": "Layered beef lasagne, baked to order.", "price": 9000, "portion": "Serves 1"},
]


class Command(BaseCommand):
    help = "Local dev only: seed Settings, staff accounts, the trading calendar, and sample dishes."

    @transaction.atomic
    def handle(self, *args, **options):
        settings = self._seed_settings()
        self._seed_staff()
        self._seed_dishes()
        days = materialise_days(now_sast().date(), settings)
        self.stdout.write(self.style.SUCCESS(
            f"Trading calendar: {days[0].date} … {days[-1].date} materialised with slots."
        ))

    def _seed_settings(self) -> Settings:
        settings, created = Settings.objects.get_or_create(
            id=1,
            defaults={"public_site_name": "Brandon's Kitchen (dev)"},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Settings: created default row."))
        else:
            self.stdout.write("Settings: row already exists, left untouched.")
        return settings

    def _seed_staff(self) -> None:
        for email, name, role in _DEV_STAFF:
            if User.objects.filter(email=email).exists():
                self.stdout.write(f"Staff: {email} already exists, skipped.")
                continue
            temp_password = secrets.token_urlsafe(9)
            User.objects.create(
                email=email,
                name=name,
                role=role,
                password_hash=hash_password(temp_password),
                must_change_password=True,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Staff: created {email} ({role}) — temporary password: {temp_password}"
            ))

    def _seed_dishes(self) -> None:
        created_count = 0
        for sort_order, spec in enumerate(_DEV_DISHES):
            dish, created = Dish.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "short_description": spec["desc"],
                    "price_cents": spec["price"],
                    "portion_label": spec["portion"],
                    "category": spec["category"],
                    "sort_order": sort_order,
                    "is_active_on_menu": True,
                    "allow_notes": True,
                },
            )
            if not created:
                continue
            created_count += 1
            for option_name, required, values in spec.get("options", []):
                option = DishOption.objects.create(dish=dish, name=option_name, required=required)
                for value_sort, (value_name, delta) in enumerate(values):
                    DishOptionValue.objects.create(
                        option=option, name=value_name, price_delta_cents=delta,
                        sort_order=value_sort,
                    )
        if created_count:
            self.stdout.write(self.style.SUCCESS(f"Dishes: created {created_count}."))
        else:
            self.stdout.write("Dishes: all already exist, skipped.")
