"""Migration: social auth foundation (D-35/D-36).

Creates:
  - staff_allowlist
  - social_identities
  - login_tokens

Also updates UserRole choices to add 'admin' (no DB change needed —
the role column is a plain CharField with no Postgres CHECK constraint
on the value set; choices enforcement is Django-layer only).
"""
from __future__ import annotations

import django.contrib.postgres.fields.citext
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_customer_password_hash"),
    ]

    operations = [
        # UserRole choices update — alters the field to reflect the new
        # 'admin' option. No DDL emitted because the column has no DB-level
        # enum constraint (it's a varchar(10)).
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                max_length=10,
                choices=[
                    ("admin", "Admin"),
                    ("owner", "Owner"),
                    ("manager", "Manager"),
                ],
            ),
        ),
        migrations.CreateModel(
            name="StaffAllowlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", django.contrib.postgres.fields.citext.CITextField(unique=True)),
                ("role", models.CharField(
                    max_length=10,
                    choices=[
                        ("admin", "Admin"),
                        ("owner", "Owner"),
                        ("manager", "Manager"),
                    ],
                )),
                ("invited_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="invitations",
                    to="core.user",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "staff_allowlist"},
        ),
        migrations.CreateModel(
            name="SocialIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=20)),
                ("uid", models.CharField(max_length=200)),
                ("email", django.contrib.postgres.fields.citext.CITextField()),
                ("staff_user", models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="social_identity",
                    to="core.user",
                )),
                ("customer", models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="social_identity",
                    to="core.customer",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "social_identities"},
        ),
        migrations.AddConstraint(
            model_name="socialidentity",
            constraint=models.UniqueConstraint(
                fields=["provider", "uid"],
                name="social_identities_provider_uid_uniq",
            ),
        ),
        migrations.CreateModel(
            name="LoginToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(max_length=64, unique=True)),
                ("email", django.contrib.postgres.fields.citext.CITextField()),
                ("intent", models.CharField(max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
            ],
            options={"db_table": "login_tokens"},
        ),
        migrations.AddIndex(
            model_name="logintoken",
            index=models.Index(fields=["token", "expires_at"], name="login_tokens_lookup_idx"),
        ),
    ]
