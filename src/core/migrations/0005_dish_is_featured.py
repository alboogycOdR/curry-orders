"""Migration: Dish.is_featured — staff-editable "this week's special"
flag for the poster variant's Home hero (previously hardcoded to the
slug "chicken-masala-roti-roll", see public/views.py::_featured_dish()
and its own updated docstring). Single additive column, default False
for every existing row; no change to any other table. At most one dish
should ever have this True at a time — enforced at the application
layer (staff/views.py), not a DB constraint, since a cross-row "at most
one" rule isn't expressible as a single-row CheckConstraint.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_order_collection_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),
    ]
