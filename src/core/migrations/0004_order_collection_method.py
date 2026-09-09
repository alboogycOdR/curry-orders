"""Migration: Order.collection_method (poster-variant checkout addition,
updates0909/handover_poster_variant open question 2 — Uber Courier is a
real selectable option). Single additive column, default 'direct' for
every existing row; no change to any other table.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_social_auth"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="collection_method",
            field=models.CharField(
                max_length=15,
                choices=[("direct", "Direct collection"), ("uber_courier", "Uber Courier (customer-arranged)")],
                default="direct",
            ),
        ),
    ]
