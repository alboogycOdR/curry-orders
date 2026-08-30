"""Forms for the staff auth flow, the (owner-only) settings editor, and
(milestone 8) daily controls.
"""
from __future__ import annotations

from django import forms

from core.models import Dish, DishOption, DishOptionValue, Settings, TradingDay

# Not a spec-mandated policy (D-12 doesn't state a minimum) — a plain
# sanity floor so "Place the order" — sorry, "Change password" — can't be
# set to something trivially guessable. Revisit if the owner wants a real
# password policy written down.
MIN_PASSWORD_LENGTH = 10


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "input", "autofocus": True})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "input"}))


class ChangePasswordForm(forms.Form):
    """Used both for the forced change-on-first-login flow
    (`users.must_change_password`, D-12) and a voluntary password change —
    both require the current password, so a hijacked but still-open
    session can't silently lock the real owner out.
    """

    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input"}), label="Current password"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input"}),
        label="New password",
        min_length=MIN_PASSWORD_LENGTH,
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input"}), label="Confirm new password"
    )

    def clean(self):
        cleaned = super().clean()
        new = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if new and confirm and new != confirm:
            self.add_error("confirm_password", "Doesn't match the new password.")
        return cleaned


class SettingsForm(forms.ModelForm):
    """Every column on the D-24 singleton row except the ones the view
    sets itself (`id` is fixed at 1; `updated_by`/`updated_at` are stamped
    on save, not user input). `ModelForm.is_valid()` runs
    `instance.full_clean()`, which (Django >=4.1, this project pins 5.0)
    includes `validate_constraints()` — so `Settings`'s own `CheckConstraint`s
    (window-before-cutoff, cash-cap-under-daily-cap, ...) are enforced here
    for free, not re-implemented as form-level validators.
    """

    class Meta:
        model = Settings
        # `exclude` over an explicit `fields` list is the right call here,
        # not the usual footgun ruff's DJ006 warns about (a new sensitive
        # field silently becoming user-editable): every Settings field is
        # meant to be owner-editable by design (D-24's whole row), so a
        # newly added one should appear on this form automatically rather
        # than be forgotten from a 40-name `fields` list.
        exclude = ["id", "updated_by", "updated_at"]  # noqa: DJ006
        widgets = {
            # Genuinely multi-line TextFields (§7.2) get a bounded
            # Textarea; every other TextField (public_site_name,
            # bank_name, account_name, branch_code, account_type,
            # vat_number, ...) is one line of text and would otherwise
            # render as Django's default full-size Textarea — a plain
            # TextInput for those instead, via __init__ below.
            "allergen_disclaimer": forms.Textarea(attrs={"rows": 3}),
            "home_kitchen_notice": forms.Textarea(attrs={"rows": 3}),
            "sms_ready_template": forms.Textarea(attrs={"rows": 3}),
            "collection_address_line": forms.Textarea(attrs={"rows": 2}),
            "collection_instructions": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ~40 fields — tagging each individually in Meta.widgets would be
        # most of this file. Checkboxes keep their native appearance (the
        # design system has no styled checkbox component); a TextField
        # Django would otherwise default to a full Textarea gets downgraded
        # to a single-line TextInput unless Meta.widgets already picked a
        # (bounded) Textarea for it above; everything else just gets the
        # system's plain-text-input look.
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            if isinstance(field.widget, forms.Textarea) and name not in self.Meta.widgets:
                field.widget = forms.TextInput()
            field.widget.attrs.setdefault("class", "input")


class TradingDayForm(forms.ModelForm):
    """§12.8's day-level fields: open/close, window/cut-off override,
    daily cap, internal notes. Per-slot capacity/close and per-dish
    availability/`max_units` are dynamic (however many slots/active
    dishes exist for the day) and are handled directly in
    `staff/views.py::daily_controls` from the raw POST, not through a
    formset — same reasoning `public/api.py`'s checkout payload parsing
    already uses for a variable-length `lines[]`.
    """

    class Meta:
        model = TradingDay
        fields = [
            "is_open", "window_start", "window_end", "cutoff_time",
            "daily_order_cap", "notes_internal",
        ]
        widgets = {
            "notes_internal": forms.Textarea(attrs={"rows": 3, "class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.CheckboxInput, forms.Textarea)):
                continue
            field.widget.attrs.setdefault("class", "input")


class DishForm(forms.ModelForm):
    """§12.7's menu editor create/edit form. `slug` is set once (§7.3:
    "slug is immutable/permalink-stable") — editable on create, but the
    field is dropped from an *edit* form entirely (`__init__` below)
    rather than merely disabled, so a crafted POST that adds the field
    back can't slip a new slug past `is_valid()`; `staff/views.py`'s
    view never copies `slug` out of the form data on an edit either,
    belt-and-braces against the same thing.
    """

    class Meta:
        model = Dish
        fields = [
            "slug", "name", "price_cents", "portion_label",
            "short_description", "long_description", "spice_default",
            "allergen_text", "dietary_tags", "category", "sort_order",
            "is_active_on_menu", "allow_notes",
        ]
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 2}),
            "long_description": forms.Textarea(attrs={"rows": 4}),
            "allergen_text": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, editing: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if editing:
            # Slug is immutable after the first save — remove it from the
            # form entirely rather than just disabling the widget.
            del self.fields["slug"]
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            if isinstance(field.widget, forms.Textarea) and name not in self.Meta.widgets:
                field.widget = forms.TextInput()
            field.widget.attrs.setdefault("class", "input")


class DishOptionForm(forms.ModelForm):
    class Meta:
        model = DishOption
        fields = ["name", "required", "sort_order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            field.widget.attrs.setdefault("class", "input")


class DishOptionValueForm(forms.ModelForm):
    class Meta:
        model = DishOptionValue
        fields = ["name", "price_delta_cents", "sort_order", "is_available"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            field.widget.attrs.setdefault("class", "input")
