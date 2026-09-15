"""Migration: User.google_avatar_url — Google's own avatar (OIDC
userinfo's "picture" claim), for the staff identity bar
(base.html/staff/views.py, 2026-09-15). Single additive column, default
NULL for every existing row; no change to any other table.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_dish_is_featured"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="google_avatar_url",
            field=models.TextField(null=True, blank=True),
        ),
    ]
