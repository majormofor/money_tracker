# finance/forms.py
# ─────────────────────────────────────────────────────────────────────────────
# All the forms for the Finance app live here.
# This file defines:
#   1) CategoryForm – create/update a Category with per-user/type uniqueness
#   2) CategoryChoiceField – custom ModelChoiceField that swallows the "_other" sentinel
#   3) TransactionForm – add/edit Transactions with:
#        - category list filtered by transaction_type (Income/Expense)
#        - "Other…" path that creates a new category under the chosen type
#        - strict server-side validation (works even if JS is off)
# Every important line is commented for learning clarity.
# ─────────────────────────────────────────────────────────────────────────────

from django import forms                                  # ← Django form building blocks
from django.core.exceptions import ValidationError        # ← To raise user-friendly errors

from .models import Category, Transaction                 # ← Your app models (FK etc.)


# ─────────────────────────────────────────────────────────────────────────────
# Helper (optional): normalize a category name (trim extra spaces)
# ─────────────────────────────────────────────────────────────────────────────
def _norm_name(name: str) -> str:
    """Return a neatly spaced version of the name (no double spaces)."""
    # Ensure we always have a string, then squash whitespace and trim.
    name = (name or "").strip()
    # Split on any whitespace and re-join with single spaces.
    return " ".join(name.split())


# ─────────────────────────────────────────────────────────────────────────────
# 1) CategoryForm
# ─────────────────────────────────────────────────────────────────────────────
class CategoryForm(forms.ModelForm):
    """
    Simple form for Category.
    - The view can pass `user=request.user` so we can enforce uniqueness per user+type.
    """

    class Meta:
        model  = Category                                              # ← Backed by Category model
        fields = ["name", "type"]                                      # ← Only name and type are editable
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Salary, Sales, Rent, Utilities"}),  # UI hint
        }

    def __init__(self, *args, **kwargs):
        # Pull the logged-in user from kwargs if provided by the view.
        self.user = kwargs.pop("user", None)                           # ← Store for later checks/saving
        super().__init__(*args, **kwargs)                              # ← Finish normal init

    def clean_name(self):
        """
        Enforce unique (case-insensitive) names per (user, type).
        Example: the same user cannot have two 'Rent' Expense categories.
        """
        # Normalize the posted name.
        name = _norm_name(self.cleaned_data.get("name"))
        # Read the chosen type ("Income" or "Expense").
        cat_type = self.cleaned_data.get("type")

        # If we know the user and have both fields, enforce uniqueness.
        if self.user and name and cat_type:
            qs = Category.objects.filter(user=self.user, type=cat_type, name__iexact=name)  # case-insensitive match
            if self.instance.pk:                                                            # when editing, ignore self
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("You already have a category with this name for this type.")
        return name

    def save(self, commit=True):
        """Make sure the Category row is tied to the user (if provided)."""
        obj = super().save(commit=False)                             # ← Build, but don’t write yet
        if self.user and not obj.user_id:                            # ← Only set if not already set
            obj.user = self.user
        if commit:
            obj.save()                                               # ← Write to DB
        return obj


# ─────────────────────────────────────────────────────────────────────────────
# 2) CategoryChoiceField – swallows the "_other" sentinel value gracefully
# ─────────────────────────────────────────────────────────────────────────────
class CategoryChoiceField(forms.ModelChoiceField):
    """
    Custom ModelChoiceField:
    - If the browser submits value "_other" (our 'Other…' sentinel), treat it as empty/None.
    - This prevents "Select a valid choice" errors before our form.clean() runs.
    """
    def to_python(self, value):
        # If no selection or the sentinel is posted, behave like 'no category selected'.
        if value in (None, "", "_other"):
            return None
        # Otherwise, let ModelChoiceField parse the PK normally.
        return super().to_python(value)


# ─────────────────────────────────────────────────────────────────────────────
# 3) TransactionForm
# ─────────────────────────────────────────────────────────────────────────────
class TransactionForm(forms.ModelForm):
    """
    Form for creating/updating a Transaction with smart category handling.
    Features:
      • Filters categories to the current user (and the selected transaction_type).
      • Supports an 'Other…' flow: user types a new category name → we create it.
      • Validates that selected category.type matches transaction_type.
      • Works even if JavaScript is off (server-side checks).
    """

    # Extra text field to capture a new category name when user chooses “Other…”
    new_category = forms.CharField(
        required=False,                                               # ← Only required when “Other…” chosen
        label="New category (if ‘Other…’)",                           # ← Clear label for the input
        widget=forms.TextInput(attrs={"placeholder": "e.g., Freelance, Groceries"}),  # UI hint
    )

    class Meta:
        model  = Transaction                                          # ← Backed by Transaction model
        fields = ["title", "amount", "transaction_type", "category", "date", "notes", "new_category"]  # ← field order
        widgets = {
            "title":  forms.TextInput(attrs={"placeholder": "Short description"}),  # nice placeholder
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),        # currency-friendly step
            "date":   forms.DateInput(attrs={"type": "date"}),                      # browser date picker
            "notes":  forms.Textarea(attrs={"rows": 3, "placeholder": "Optional notes"}),  # small text area
        }

    def __init__(self, *args, **kwargs):
        # Expect the view to pass `user=request.user` so we can: filter categories, set Transaction.user, etc.
        self.user = kwargs.pop("user", None)                                       # ← Save logged-in user
        super().__init__(*args, **kwargs)                                          # ← Normal init

        # Build a base queryset of categories for this user (or empty if no user provided).
        base_qs = Category.objects.none()                                          # ← Start with empty set
        if self.user:                                                              # ← If a user is known…
            base_qs = Category.objects.filter(user=self.user).order_by("name")     # ← …limit to their categories

        # Determine the chosen transaction type now (POST takes priority, then instance when editing).
        tx_type = self.data.get("transaction_type") or getattr(self.instance, "transaction_type", None)

        # Replace the auto-built ModelChoiceField with our safe CategoryChoiceField.
        # This field:
        #   - uses a filtered queryset,
        #   - is NOT required (user may type a new category instead),
        #   - has a friendly "Choose existing…" empty option,
        #   - and treats "_other" as empty (no ValidationError).
        self.fields["category"] = CategoryChoiceField(
            queryset=base_qs.filter(type=tx_type) if tx_type in ("Income", "Expense") else base_qs,  # filter by type
            required=False,                                                                          # allow blank
            empty_label="Choose existing…",                                                          # UX hint
        )

    def clean(self):
        """
        Cross-field validation:
          - User must choose an existing category OR type a new one.
          - If an existing category is chosen, it must match the selected transaction_type.
          - If both are provided, ask the user to pick one path.
        """
        cleaned   = super().clean()                                            # ← Let default cleaning run first
        tx_type   = cleaned.get("transaction_type")                            # ← "Income" or "Expense"
        category  = cleaned.get("category")                                    # ← FK Category (or None)
        new_cat   = _norm_name(cleaned.get("new_category"))                    # ← Normalize typed name

        # If the user didn't choose a category and didn't type a new one → error.
        if not category and not new_cat:
            raise ValidationError("Pick a category or type a new one.")

        # If they provided both → gently correct (prefer the chosen category).
        if category and new_cat:
            self.add_error("new_category", "Leave this blank if you choose an existing category.")

        # If an existing category is chosen, its type must match the transaction_type.
        if category and tx_type and category.type != tx_type:
            self.add_error("category", f"Selected category is '{category.type}'. It must match '{tx_type}'.")

        return cleaned                                                         # ← Return the cleaned data dict

    def save(self, commit=True):
        """
        Ensure:
        - Transaction.user is set.
        - If no existing category was chosen but new_category was typed,
        create (or reuse) it with the correct type, then assign to the transaction.
        """
        obj = super().save(commit=False)  # build but don't write yet

        # Always bind to the logged-in user (if provided)
        if self.user:
            obj.user = self.user

        # ⚠️ IMPORTANT: check the FK id, not the relation
        # Accessing obj.category here can raise RelatedObjectDoesNotExist if it's unset.
        if not getattr(obj, "category_id", None):
            name    = _norm_name(self.cleaned_data.get("new_category"))
            tx_type = self.cleaned_data.get("transaction_type")

            if name:
                # Try to reuse an existing category (case-insensitive) for this user+type
                cat = None
                if self.user:
                    cat = Category.objects.filter(
                        user=self.user, name__iexact=name, type=tx_type
                    ).first()
                if not cat:
                    if not self.user:
                        # Cannot create a user-owned category without a user context
                        raise ValidationError("Cannot create a category without a user context.")
                    cat = Category.objects.create(user=self.user, name=name, type=tx_type)
                obj.category = cat

        if commit:
            obj.save()
        return obj                                                        # ← Return the saved (or unsaved) object
