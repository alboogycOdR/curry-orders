"""Domain model — a faithful Django ORM translation of `schema_v1_1.sql`
(spec §7). Per the spec's own precedence rule ("Where this document and
`schema_v1_1.sql` disagree, the SQL wins for structure"), this file
follows the SQL's table/column/constraint shape, not spec prose, wherever
the two could be read differently.

`core/` has no HTTP imports (§17.2). This module is models only — no
capacity/transition/ordering logic. That belongs to `core/capacity.py`
(§8), `core/transitions.py` (§9) and `core/ordering.py` (order-number
formatting, `option_key` derivation — D-29), all out of scope for this
milestone and deliberately not started here beyond the TODO markers below.

--- Documented deviations from schema_v1_1.sql (candidate DECISIONS.md entries) ---

1. Enum columns (`order_status`, `payment_method`, `payment_status`,
   `cancellation_reason`, `actor_kind`, `media_kind`, `order_source`,
   `user_role`) are modelled as `CharField` + `TextChoices`, not native
   Postgres `ENUM` types. Django has no first-class enum field; matching
   `CREATE TYPE ... AS ENUM` verbatim would mean a custom field plus a
   raw-SQL migration per enum, for no behavioural difference from a
   `CharField` sized to the longest member (values match the SQL exactly,
   enforced at the DB level only insofar as the column's `choices` are a
   Django-level, not Postgres-level, constraint). Flagging as a candidate
   decision rather than silently diverging from "SQL wins for structure".

2. `day_dish_availability` has no composite primary key. Django's ORM
   does not support composite primary keys before 5.2 (this project pins
   `django>=5.0,<5.1` in pyproject.toml). Modelled with an implicit
   surrogate `BigAutoField id` plus `UniqueConstraint(trading_day, dish)`,
   which reproduces the SQL's `PRIMARY KEY (trading_day, dish_id)`
   uniqueness semantics exactly (both columns are already NOT NULL via
   their FKs). Revisit if/when the project moves to Django 5.2+.

3. `order_lines.option_key` is intentionally NOT derived at the DB layer
   — see D-29 and the TODO on the field itself.

4. Bounded schema `text` columns with an explicit CHECK upper bound on
   length (e.g. `name BETWEEN 1 AND 80`) are modelled as `CharField` with
   a matching `max_length` (DB-enforced via `varchar(N)`) plus a
   `CheckConstraint` regex for any lower bound. Schema `text` columns
   with *no* CHECK, or a CHECK with only a lower bound (e.g.
   `public_token`'s `length >= 22`) or a shape-only regex (e.g.
   `dishes.slug`), are modelled as `TextField` so no artificial upper
   bound is introduced that the SQL does not itself impose.

--- Not modelled here — explicitly deferred (do not build in this pass) ---

* The four capacity views (`v_occupying_orders`, `v_day_occupancy`,
  `v_slot_occupancy`, `v_dish_units_used`) and `v_kitchen_summary`: these
  are read-side SQL, not tables. They will be added as raw-SQL
  `migrations.RunSQL` (mirroring the SQL in schema_v1_1.sql §8.1/§9.3/
  §12.4) once `core/capacity.py` needs them, or queried directly with
  raw SQL from that module — whichever `capacity.py`'s implementation
  finds cleaner. Not guessed at here.
* `next_order_number(p_day date)` (the Postgres function backing D-04)
  and the `touch_updated_at` triggers (`dishes_touch`, `orders_touch`,
  `trading_days_touch`): same treatment — a TODO for a later raw-SQL
  migration. `updated_at` columns below use Django's `auto_now=True` so
  ORM-driven updates already get a correct timestamp; the trigger would
  only additionally cover updates made outside the ORM (e.g. a manual
  `UPDATE` in a psql session), which is why schema_v1_1.sql has it as a
  DB-level belt-and-braces guarantee. Not a substitute for
  `core/ordering.py` / `core/transitions.py` (milestone 3), which is
  where `updated_at`-on-write actually gets exercised in anger.
"""
from __future__ import annotations

from django.contrib.postgres.fields import ArrayField, CITextField
from django.db import models
from django.db.models.expressions import RawSQL

# ---------------------------------------------------------------- enums (§7, schema CREATE TYPE)


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    OWNER = "owner", "Owner"
    MANAGER = "manager", "Manager"


class OrderSource(models.TextChoices):
    WEBSITE = "website", "Website"
    WHATSAPP_ASSISTED = "whatsapp_assisted", "WhatsApp (assisted)"
    PHONE = "phone", "Phone"
    IN_PERSON = "in_person", "In person"


class OrderStatus(models.TextChoices):
    AWAITING_EFT = "awaiting_eft", "Awaiting EFT"
    PAYMENT_REVIEW = "payment_review", "Payment review"
    CONFIRMED_PREP = "confirmed_prep", "Confirmed (prep)"
    CASH_REQUEST = "cash_request", "Cash request"
    CASH_DUE = "cash_due", "Cash due"
    IN_KITCHEN = "in_kitchen", "In kitchen"
    READY = "ready", "Ready"
    COLLECTED = "collected", "Collected"
    PAYMENT_EXPIRED = "payment_expired", "Payment expired"
    CANCELLED = "cancelled", "Cancelled"


class PaymentMethod(models.TextChoices):
    EFT = "eft", "EFT"
    CASH = "cash", "Cash"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    UNDER_REVIEW = "under_review", "Under review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"
    COLLECTED_CASH = "collected_cash", "Collected (cash)"
    CANCELLED = "cancelled", "Cancelled"


class CancellationReason(models.TextChoices):
    CUSTOMER_REQUEST = "customer_request", "Customer request"
    STAFF = "staff", "Staff"
    CASH_REJECTED = "cash_rejected", "Cash rejected"
    PAYMENT_REJECTED = "payment_rejected", "Payment rejected"
    NO_SHOW = "no_show", "No-show"
    DAY_CLOSED = "day_closed", "Day closed"
    DUPLICATE = "duplicate", "Duplicate"
    OWNER_EXCEPTION = "owner_exception", "Owner exception"
    OTHER = "other", "Other"


class ActorKind(models.TextChoices):
    STAFF = "staff", "Staff"
    CUSTOMER = "customer", "Customer"
    SYSTEM = "system", "System"


class MediaKind(models.TextChoices):
    PROOF = "proof", "Proof"
    DISH_IMAGE = "dish_image", "Dish image"


# ---------------------------------------------------------------- staff (§7.1)


class User(models.Model):
    """Staff (owner/manager) account. Not django.contrib.auth's User —
    schema_v1_1.sql defines its own shape (`password_hash`, no username).
    Password hashing/lockout: `core.auth`. Session auth: `staff.sessions`
    + `StaffSessionMiddleware` (`request.staff_user`) — a fully custom
    mechanism on top of Django's session store rather than
    `django.contrib.auth`; see docs/DECISIONS.md D-33 for why, and §4 for
    the D-12 rules it implements.
    """

    # CITextField -> Postgres citext, matching schema_v1_1.sql exactly
    # ("email citext NOT NULL UNIQUE"). Django's system check flags this
    # as deprecated (W907) as of 5.0, removal not until 5.1; pyproject.toml
    # pins django>=5.0,<5.1, so it stays available for this project's
    # lifetime on that pin. The suggested replacement (a TextField with a
    # non-deterministic case-insensitive db_collation) is a reasonable
    # follow-up if/when the Django pin moves, not before.
    email = CITextField(unique=True)
    name = models.CharField(max_length=80)
    role = models.CharField(max_length=10, choices=UserRole.choices)
    password_hash = models.TextField()
    active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=True)
    failed_login_count = models.SmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(
                check=models.Q(name__regex=r"^.{1,80}$"),
                name="users_name_length",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"


class StaffAllowlist(models.Model):
    """Emails permitted to sign in as staff via Google/magic-link OAuth.
    Admin manages this via /manage/team/. An email in this list that has
    no matching core.User yet gets one created on first social login.
    """
    email = CITextField(unique=True)
    role = models.CharField(max_length=10, choices=UserRole.choices)
    invited_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="invitations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_allowlist"

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"


class SocialIdentity(models.Model):
    """A verified social (Google) identity. Links to exactly one of:
    staff_user (core.User) or customer (core.Customer). Both nullable so
    an identity can exist before the link is resolved (e.g. a new Google
    customer who has not yet provided their mobile).
    """
    provider = models.CharField(max_length=20)        # "google"
    uid = models.CharField(max_length=200)             # Google 'sub'
    email = CITextField()
    staff_user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name="social_identity"
    )
    customer = models.OneToOneField(
        "Customer", null=True, blank=True, on_delete=models.SET_NULL, related_name="social_identity"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_identities"
        constraints = [
            models.UniqueConstraint(fields=["provider", "uid"], name="social_identities_provider_uid_uniq"),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.uid} ({self.email})"


class LoginToken(models.Model):
    """Short-lived token for email magic-link auth (15-minute window).
    intent='staff' tokens log in core.User; intent='customer' tokens
    log in core.Customer. Used once (used_at set on consume).
    """
    token = models.CharField(max_length=64, unique=True)
    email = CITextField()
    intent = models.CharField(max_length=10)           # 'staff' | 'customer'
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "login_tokens"
        indexes = [
            models.Index(fields=["token", "expires_at"], name="login_tokens_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.intent}:{self.email}"


# ---------------------------------------------------------------- settings (§7.2, single row)


class Settings(models.Model):
    """Single typed row (`id = 1` enforced by CHECK, D-24). Every save
    should also write a SettingsEvent diff — that's application logic
    (a later milestone), not enforced here.
    """

    id = models.SmallIntegerField(primary_key=True, default=1)

    public_site_name = models.TextField()
    collection_address_line = models.TextField(null=True, blank=True)
    collection_instructions = models.TextField(null=True, blank=True)
    bank_name = models.TextField(null=True, blank=True)
    account_name = models.TextField(null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    branch_code = models.TextField(null=True, blank=True)
    account_type = models.TextField(null=True, blank=True)

    default_window_start = models.TimeField(default="16:00")
    default_window_end = models.TimeField(default="18:00")
    slot_minutes = models.SmallIntegerField(default=15)
    default_slot_capacity = models.SmallIntegerField(default=13)
    default_daily_order_cap = models.SmallIntegerField(default=100)
    same_day_cutoff = models.TimeField(default="10:00")
    preorder_days = models.SmallIntegerField(default=7)
    eft_hold_minutes = models.SmallIntegerField(default=30)
    max_hold_extensions = models.SmallIntegerField(default=1)
    hold_extension_minutes = models.SmallIntegerField(default=15)
    payment_review_sla_minutes = models.SmallIntegerField(default=15)

    cash_enabled = models.BooleanField(default=True)
    cash_same_day_only = models.BooleanField(default=True)
    cash_daily_cap = models.SmallIntegerField(default=20)

    collection_grace_minutes = models.SmallIntegerField(default=15)
    assisted_after_cutoff_enabled = models.BooleanField(default=False)
    support_whatsapp_e164 = models.CharField(max_length=16, null=True, blank=True)

    allergen_disclaimer = models.TextField(null=True, blank=True)
    home_kitchen_notice = models.TextField(null=True, blank=True)

    vat_registered = models.BooleanField(default=False)
    vat_number = models.TextField(null=True, blank=True)

    proof_retention_days = models.SmallIntegerField(default=90)
    order_retention_months = models.SmallIntegerField(default=18)

    sms_enabled = models.BooleanField(default=False)
    sms_ready_template = models.TextField(
        default=(
            "{site}: order {order_number} is ready. Collect {slot_label} "
            "at {address_line}. {instructions}"
        )
    )

    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="+",
        db_column="updated_by",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "settings"
        constraints = [
            models.CheckConstraint(check=models.Q(id=1), name="settings_id_is_1"),
            models.CheckConstraint(
                check=models.Q(account_number__isnull=True)
                | models.Q(account_number__regex=r"^[0-9]{6,20}$"),
                name="settings_account_number_format",
            ),
            models.CheckConstraint(
                check=models.Q(slot_minutes__gte=5) & models.Q(slot_minutes__lte=60),
                name="settings_slot_minutes_range",
            ),
            models.CheckConstraint(
                check=models.Q(default_slot_capacity__gte=1),
                name="settings_default_slot_capacity_min",
            ),
            models.CheckConstraint(
                check=models.Q(default_daily_order_cap__gte=1),
                name="settings_default_daily_order_cap_min",
            ),
            models.CheckConstraint(
                check=models.Q(preorder_days__gte=0) & models.Q(preorder_days__lte=14),
                name="settings_preorder_days_range",
            ),
            models.CheckConstraint(
                check=models.Q(eft_hold_minutes__gte=5) & models.Q(eft_hold_minutes__lte=120),
                name="settings_eft_hold_minutes_range",
            ),
            models.CheckConstraint(
                check=models.Q(max_hold_extensions__gte=0) & models.Q(max_hold_extensions__lte=3),
                name="settings_max_hold_extensions_range",
            ),
            models.CheckConstraint(
                check=models.Q(hold_extension_minutes__gte=5)
                & models.Q(hold_extension_minutes__lte=60),
                name="settings_hold_extension_minutes_range",
            ),
            models.CheckConstraint(
                check=models.Q(payment_review_sla_minutes__gte=5)
                & models.Q(payment_review_sla_minutes__lte=120),
                name="settings_payment_review_sla_minutes_range",
            ),
            models.CheckConstraint(
                check=models.Q(cash_daily_cap__gte=0),
                name="settings_cash_daily_cap_min",
            ),
            models.CheckConstraint(
                check=models.Q(collection_grace_minutes__gte=0)
                & models.Q(collection_grace_minutes__lte=60),
                name="settings_collection_grace_minutes_range",
            ),
            models.CheckConstraint(
                check=models.Q(support_whatsapp_e164__isnull=True)
                | models.Q(support_whatsapp_e164__regex=r"^\+[1-9][0-9]{7,14}$"),
                name="settings_support_whatsapp_format",
            ),
            models.CheckConstraint(
                check=models.Q(proof_retention_days__gte=30)
                & models.Q(proof_retention_days__lte=365),
                name="settings_proof_retention_days_range",
            ),
            models.CheckConstraint(
                check=models.Q(order_retention_months__gte=6)
                & models.Q(order_retention_months__lte=60),
                name="settings_order_retention_months_range",
            ),
            models.CheckConstraint(
                check=models.Q(default_window_start__lt=models.F("default_window_end")),
                name="settings_window_start_before_end",
            ),
            models.CheckConstraint(
                check=models.Q(same_day_cutoff__lt=models.F("default_window_start")),
                name="settings_cutoff_before_window_start",
            ),
            models.CheckConstraint(
                check=models.Q(cash_daily_cap__lte=models.F("default_daily_order_cap")),
                name="settings_cash_cap_le_daily_cap",
            ),
            models.CheckConstraint(
                check=models.Q(vat_registered=False) | models.Q(vat_number__isnull=False),
                name="settings_vat_number_required_if_registered",
            ),
        ]

    def __str__(self) -> str:
        return self.public_site_name or "Settings"

    @classmethod
    def current(cls) -> "Settings":
        """The singleton row (`id=1`, D-24) if `/manage/settings` has ever
        been saved, else an unsaved `Settings()` carrying the field
        defaults declared above — so read-only display code (the public
        site's hero figures, the kitchen desk's service window, ...) has
        something sane to render in a pre-seed dev/pilot environment
        instead of crashing on a missing row. Never persisted from here;
        callers that need to *write* settings still go through the real
        row plus a `SettingsEvent` diff (that's application logic, D-24).
        """
        return cls.objects.filter(pk=1).first() or cls()


class SettingsEvent(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="settings_events"
    )
    diff = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "settings_events"


# ---------------------------------------------------------------- media (§7.13)


class Media(models.Model):
    kind = models.CharField(max_length=10, choices=MediaKind.choices)
    storage_key = models.TextField(unique=True)
    mime_type = models.TextField()
    byte_size = models.IntegerField()
    sha256 = models.BinaryField()
    # FKs added after `orders`/`dishes` in the SQL via ALTER TABLE; declared
    # directly here since Django resolves same-app circular refs itself.
    order = models.ForeignKey(
        "Order", null=True, blank=True, on_delete=models.CASCADE, related_name="media_files"
    )
    dish = models.ForeignKey(
        "Dish", null=True, blank=True, on_delete=models.SET_NULL, related_name="media_files"
    )
    uploaded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="+",
        db_column="uploaded_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "media"
        constraints = [
            models.CheckConstraint(
                check=models.Q(byte_size__gt=0) & models.Q(byte_size__lte=8 * 1024 * 1024),
                name="media_byte_size_range",
            ),
            models.CheckConstraint(
                check=~models.Q(kind=MediaKind.PROOF)
                | models.Q(
                    mime_type__in=[
                        "image/jpeg",
                        "image/png",
                        "image/webp",
                        "application/pdf",
                    ]
                ),
                name="media_proof_mime_type",
            ),
            models.CheckConstraint(
                check=~models.Q(kind=MediaKind.DISH_IMAGE)
                | models.Q(mime_type__in=["image/jpeg", "image/png", "image/webp"]),
                name="media_dish_image_mime_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.storage_key}"


# ---------------------------------------------------------------- menu (§7.3, §7.4)


class Dish(models.Model):
    slug = models.TextField(unique=True)
    name = models.CharField(max_length=80)
    short_description = models.TextField(null=True, blank=True)
    long_description = models.TextField(null=True, blank=True)
    price_cents = models.IntegerField()
    portion_label = models.TextField(null=True, blank=True)
    spice_default = models.TextField(null=True, blank=True)
    allergen_text = models.TextField(null=True, blank=True)
    dietary_tags = ArrayField(models.TextField(), default=list, blank=True)
    image_media = models.ForeignKey(
        Media, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="+"
    )
    image_alt = models.TextField(null=True, blank=True)
    category = models.TextField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    is_active_on_menu = models.BooleanField(default=False)
    allow_notes = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # TODO: see module docstring re touch_updated_at

    class Meta:
        db_table = "dishes"
        constraints = [
            models.CheckConstraint(
                check=models.Q(slug__regex=r"^[a-z0-9]+(-[a-z0-9]+)*$"),
                name="dishes_slug_format",
            ),
            models.CheckConstraint(
                check=models.Q(name__regex=r"^.{1,80}$"),
                name="dishes_name_length",
            ),
            models.CheckConstraint(
                check=models.Q(price_cents__gte=0),
                name="dishes_price_cents_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class DishOption(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=40)
    required = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "dish_options"
        constraints = [
            models.UniqueConstraint(fields=["dish", "name"], name="dish_options_dish_name_uniq"),
            models.CheckConstraint(
                check=models.Q(name__regex=r"^.{1,40}$"),
                name="dish_options_name_length",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.dish.name} / {self.name}"


class DishOptionValue(models.Model):
    option = models.ForeignKey(DishOption, on_delete=models.CASCADE, related_name="values")
    name = models.CharField(max_length=40)
    price_delta_cents = models.IntegerField(default=0)
    sort_order = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = "dish_option_values"
        constraints = [
            models.UniqueConstraint(
                fields=["option", "name"], name="dish_option_values_option_name_uniq"
            ),
            models.CheckConstraint(
                check=models.Q(name__regex=r"^.{1,40}$"),
                name="dish_option_values_name_length",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.option.name}: {self.name}"


# ---------------------------------------------------------------- trading calendar (§7.5-§7.7)


class TradingDay(models.Model):
    """PK is the SAST calendar date itself, not a synthetic id — matches
    `trading_days.date date PRIMARY KEY` exactly."""

    date = models.DateField(primary_key=True)
    is_open = models.BooleanField(default=True)
    window_start = models.TimeField()
    window_end = models.TimeField()
    cutoff_time = models.TimeField()
    daily_order_cap = models.SmallIntegerField()
    next_order_seq = models.IntegerField(default=1)
    kitchen_locked_at = models.DateTimeField(null=True, blank=True)
    kitchen_locked_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="+",
        db_column="kitchen_locked_by",
    )
    closed_out_at = models.DateTimeField(null=True, blank=True)
    closed_out_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="+",
        db_column="closed_out_by",
    )
    notes_internal = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # TODO: see module docstring re touch_updated_at

    class Meta:
        db_table = "trading_days"
        constraints = [
            models.CheckConstraint(
                check=models.Q(window_start__lt=models.F("window_end")),
                name="trading_days_window_start_before_end",
            ),
            models.CheckConstraint(
                check=models.Q(daily_order_cap__gte=0),
                name="trading_days_daily_order_cap_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(next_order_seq__gte=1) & models.Q(next_order_seq__lte=10000),
                name="trading_days_next_order_seq_range",
            ),
        ]

    def __str__(self) -> str:
        return self.date.isoformat()


class Slot(models.Model):
    trading_day = models.ForeignKey(
        TradingDay,
        on_delete=models.CASCADE,
        related_name="slots",
        db_column="trading_day",
    )
    start_at = models.TimeField()
    end_at = models.TimeField()
    capacity = models.SmallIntegerField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        db_table = "slots"
        constraints = [
            models.UniqueConstraint(
                fields=["trading_day", "start_at"], name="slots_trading_day_start_at_uniq"
            ),
            models.CheckConstraint(
                check=models.Q(start_at__lt=models.F("end_at")),
                name="slots_start_before_end",
            ),
            models.CheckConstraint(
                check=models.Q(capacity__gte=0),
                name="slots_capacity_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.trading_day_id} {self.start_at}-{self.end_at}"


class DayDishAvailability(models.Model):
    """No composite PK — see deviation note #2 in the module docstring.
    `UniqueConstraint(trading_day, dish)` reproduces the SQL's
    `PRIMARY KEY (trading_day, dish_id)`.
    """

    trading_day = models.ForeignKey(
        TradingDay,
        on_delete=models.CASCADE,
        related_name="dish_availability",
        db_column="trading_day",
    )
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="day_availability")
    is_available = models.BooleanField(default=True)
    max_units = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "day_dish_availability"
        constraints = [
            models.UniqueConstraint(
                fields=["trading_day", "dish"], name="day_dish_availability_pk_uniq"
            ),
            models.CheckConstraint(
                check=models.Q(max_units__isnull=True) | models.Q(max_units__gte=0),
                name="day_dish_availability_max_units_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.trading_day_id} / {self.dish.name}"


# ---------------------------------------------------------------- customers & orders (§7.8, §7.9)


class Customer(models.Model):
    full_name = models.CharField(max_length=80)
    mobile_e164 = models.CharField(max_length=15, unique=True)
    # Customer accounts use the existing mobile identity.  Nullable keeps
    # historic/order-only customers valid until they choose to sign up.
    password_hash = models.TextField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_order_at = models.DateTimeField(null=True, blank=True)
    order_count = models.IntegerField(default=0)
    anonymised_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "customers"
        constraints = [
            models.CheckConstraint(
                check=models.Q(full_name__regex=r"^.{2,80}$"),
                name="customers_full_name_length",
            ),
            models.CheckConstraint(
                check=models.Q(mobile_e164__regex=r"^\+27[6-8][0-9]{8}$"),
                name="customers_mobile_e164_format",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.mobile_e164})"


class Order(models.Model):
    order_number = models.CharField(max_length=15, unique=True)
    public_token = models.TextField(unique=True)
    source = models.CharField(max_length=20, choices=OrderSource.choices)
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    # Plain "text NOT NULL" in the SQL, no length/format CHECK — the
    # E.164 shape is validated at the application layer (core/phone.py)
    # before insert, not enforced here as a DB constraint (schema_v1_1.sql
    # only puts that CHECK on customers.mobile_e164, not on this snapshot).
    customer_name_snapshot = models.TextField()
    customer_mobile_snapshot = models.TextField()
    note = models.CharField(max_length=200, null=True, blank=True)
    trading_day = models.ForeignKey(
        TradingDay,
        on_delete=models.DO_NOTHING,
        related_name="orders",
        db_column="trading_day",
    )
    slot = models.ForeignKey(Slot, on_delete=models.DO_NOTHING, related_name="orders")
    status = models.CharField(max_length=20, choices=OrderStatus.choices)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    subtotal_cents = models.IntegerField()
    discount_cents = models.IntegerField(default=0)
    total_cents = models.IntegerField()
    balance_due_cents = models.IntegerField(default=0)
    refund_note = models.TextField(null=True, blank=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    hold_extensions = models.SmallIntegerField(default=0)
    dish_units_consumed = models.BooleanField(default=False)
    dispute_flag = models.BooleanField(default=False)
    after_cutoff_reason = models.TextField(null=True, blank=True)
    assigned_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="assigned_orders"
    )
    cancellation_reason = models.CharField(
        max_length=20, choices=CancellationReason.choices, null=True, blank=True
    )
    cancellation_note = models.TextField(null=True, blank=True)
    created_by_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="created_orders",
        help_text="Null for website orders.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # TODO: see module docstring re touch_updated_at
    confirmed_at = models.DateTimeField(null=True, blank=True)
    in_kitchen_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders"
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    total_cents=models.F("subtotal_cents") - models.F("discount_cents")
                ),
                name="orders_total_equals_subtotal_minus_discount",
            ),
            models.CheckConstraint(
                check=~models.Q(status=OrderStatus.CANCELLED)
                | models.Q(cancellation_reason__isnull=False),
                name="orders_cancelled_requires_reason",
            ),
            models.CheckConstraint(
                check=~models.Q(status=OrderStatus.AWAITING_EFT)
                | models.Q(hold_expires_at__isnull=False),
                name="orders_awaiting_eft_requires_hold_expiry",
            ),
            models.CheckConstraint(
                check=models.Q(payment_method=PaymentMethod.EFT)
                | models.Q(hold_expires_at__isnull=True),
                name="orders_hold_expiry_only_for_eft",
            ),
            models.CheckConstraint(
                check=models.Q(dish_units_consumed=False)
                | models.Q(in_kitchen_at__isnull=False),
                name="orders_dish_units_consumed_requires_in_kitchen_at",
            ),
            models.CheckConstraint(
                check=models.Q(subtotal_cents__gte=0),
                name="orders_subtotal_cents_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(discount_cents__gte=0),
                name="orders_discount_cents_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(total_cents__gte=0),
                name="orders_total_cents_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(balance_due_cents__gte=0),
                name="orders_balance_due_cents_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(hold_extensions__gte=0),
                name="orders_hold_extensions_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(order_number__regex=r"^CT-[0-9]{6}-[0-9]{4}$"),
                name="orders_order_number_format",
            ),
            models.CheckConstraint(
                check=models.Q(public_token__regex=r"^.{22,}$"),
                name="orders_public_token_min_length",
            ),
        ]
        indexes = [
            # Composite / partial / non-FK indexes only — Django already
            # adds a single-column index for every plain ForeignKey (e.g.
            # customer, slot), which covers what schema_v1_1.sql's
            # single-column orders_customer_idx etc. do; recreating those
            # verbatim here would just duplicate an index Postgres already
            # has under a different auto-generated name.
            models.Index(fields=["trading_day", "status"], name="orders_day_status_idx"),
            models.Index(fields=["slot", "status"], name="orders_slot_status_idx"),
            models.Index(
                fields=["hold_expires_at"],
                name="orders_hold_idx",
                condition=models.Q(status=OrderStatus.AWAITING_EFT),
            ),
            models.Index(fields=["customer_mobile_snapshot"], name="orders_mobile_idx"),
            models.Index(fields=["created_at"], name="orders_created_idx"),
        ]

    def __str__(self) -> str:
        return self.order_number


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    dish = models.ForeignKey(
        Dish, null=True, blank=True, on_delete=models.SET_NULL, related_name="order_lines"
    )
    dish_name_snapshot = models.TextField()
    unit_price_cents_snapshot = models.IntegerField()
    quantity = models.IntegerField()
    options_snapshot = models.JSONField(default=list)
    # "Spice=Mild|Starch=Rice", options sorted by name; used for kitchen grouping.
    # TODO (D-29): compute in core/ordering.py on save — sorted
    # "Option=Value|..." string, not enforced at the DB layer. This field
    # is a plain application-set column (schema_v1_1.sql declares it
    # `text NOT NULL DEFAULT ''`, not GENERATED ALWAYS AS (...) STORED),
    # deliberately not computed here — see D-29.
    option_key = models.CharField(max_length=250, default="")
    line_total_cents = models.IntegerField()
    kitchen_note = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "order_lines"
        constraints = [
            models.CheckConstraint(
                check=models.Q(unit_price_cents_snapshot__gte=0),
                name="order_lines_unit_price_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gte=1) & models.Q(quantity__lte=20),
                name="order_lines_quantity_range",
            ),
            models.CheckConstraint(
                check=models.Q(line_total_cents__gte=0),
                name="order_lines_line_total_non_negative",
            ),
            # Django's system check (models.W045) warns that a RawSQL-based
            # CheckConstraint isn't evaluated by full_clean() — expected
            # and harmless here: the DB itself still enforces it (verified
            # via `python manage.py migrate` against real Postgres), and
            # this project's writes to options_snapshot happen through
            # core/ordering.py (D-29, milestone 3), not admin forms.
            models.CheckConstraint(
                check=RawSQL(
                    "jsonb_typeof(options_snapshot) = 'array'",
                    (),
                    output_field=models.BooleanField(),
                ),
                name="order_lines_options_snapshot_is_array",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.dish_name_snapshot} x{self.quantity}"


# ---------------------------------------------------------------- payments (§7.11)


class Payment(models.Model):
    """Exactly one row per order (`order_id` UNIQUE in the SQL) — modelled
    as a OneToOneField."""

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    amount_cents = models.IntegerField()
    reference = models.TextField()
    current_proof_media = models.ForeignKey(
        Media, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="+"
    )
    customer_declared_ref = models.TextField(null=True, blank=True)
    proof_uploaded_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="+",
        db_column="verified_by",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(null=True, blank=True)
    cash_received_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="+",
        db_column="cash_received_by",
    )
    cash_received_at = models.DateTimeField(null=True, blank=True)
    cash_amount_received_cents = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_cents__gte=0),
                name="payments_amount_cents_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(cash_amount_received_cents__isnull=True)
                | models.Q(cash_amount_received_cents__gte=0),
                name="payments_cash_amount_received_non_negative",
            ),
            models.CheckConstraint(
                check=~models.Q(status=PaymentStatus.VERIFIED)
                | (
                    models.Q(verified_by__isnull=False)
                    & models.Q(verified_at__isnull=False)
                ),
                name="payments_verified_requires_verifier_and_time",
            ),
            models.CheckConstraint(
                check=~models.Q(status=PaymentStatus.COLLECTED_CASH)
                | (
                    models.Q(cash_received_by__isnull=False)
                    & models.Q(cash_received_at__isnull=False)
                    & models.Q(cash_amount_received_cents__isnull=False)
                ),
                name="payments_collected_cash_requires_receipt_fields",
            ),
        ]

    def __str__(self) -> str:
        return f"payment for {self.order_id}"


# ---------------------------------------------------------------- audit (§7.12)


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(
        max_length=20, choices=OrderStatus.choices, null=True, blank=True
    )
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices, null=True, blank=True)
    action = models.TextField()
    actor_kind = models.CharField(max_length=10, choices=ActorKind.choices)
    actor_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="order_events"
    )
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_events"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(actor_kind=ActorKind.STAFF) | models.Q(actor_user__isnull=False),
                name="order_events_staff_requires_actor_user",
            ),
        ]
        indexes = [
            models.Index(fields=["order", "occurred_at"], name="order_events_order_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.from_status} -> {self.to_status} ({self.action})"


# ---------------------------------------------------------------- infrastructure tables (§7.14-§7.16)


class IdempotencyKey(models.Model):
    key = models.TextField(primary_key=True)
    request_sha256 = models.BinaryField()
    order = models.ForeignKey(
        Order, null=True, blank=True, on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    response_status = models.SmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_keys"
        indexes = [
            models.Index(fields=["created_at"], name="idempotency_keys_created_idx"),
        ]


class ThrottleEvent(models.Model):
    """scope: checkout_ip | proof_token | lookup_ip | lookup_order | login_email (§7.15)."""

    scope = models.TextField()
    key = models.TextField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "throttle_events"
        indexes = [
            models.Index(fields=["scope", "key", "occurred_at"], name="throttle_events_lookup_idx"),
        ]


class JobHeartbeat(models.Model):
    job_name = models.TextField(primary_key=True)
    last_run_at = models.DateTimeField()
    last_ok = models.BooleanField()
    detail = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "job_heartbeats"

    def __str__(self) -> str:
        return f"{self.job_name} ({'ok' if self.last_ok else 'FAILING'})"
