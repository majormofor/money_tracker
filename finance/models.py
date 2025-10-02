# finance/models.py

# ✅ Import Django utilities for building models
from django.db import models                        # core Django ORM classes
from django.conf import settings                    # lets us reference the current User model safely
from django.core.validators import MinValueValidator # to make sure amounts are positive
from django.utils import timezone                   # to give a sensible default date (today)
from decimal import Decimal                         # accurate money math
from django.core.exceptions import ValidationError

# ✅ We use a simple 2-choice field to indicate Income or Expense everywhere
TRANSACTION_TYPES = (
    ("Income", "Income"),     # stored value, human-readable label
    ("Expense", "Expense"),
)

class Category(models.Model):
    """
    A user-owned label to group transactions.
    Example names: Salary, Rent, Groceries, Sales.
    The 'type' (Income/Expense) ensures correct grouping in reports.
    """

    # ✅ Link each category to the user who owns it (so users don't see each other's data)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,                 # points to Django's User model
        on_delete=models.CASCADE,                 # if the user is deleted, delete their categories
        related_name="categories",                # enables user.categories.all()
        help_text="Owner of this category",
    )

    # ✅ Short, friendly name shown in dropdowns
    name = models.CharField(
        max_length=50,                            # keeps names tidy; adjust if you need longer
        help_text="e.g., Salary, Rent, Groceries",
    )

    # ✅ This category is either for Income or for Expense (never both)
    type = models.CharField(
        max_length=7,                             # "Income" or "Expense" fits in 7 chars
        choices=TRANSACTION_TYPES,                # restrict to allowed values
        help_text="Choose whether this category is for Income or Expense",
    )

    # ✅ Optional timestamps for sorting/auditing
    created_at = models.DateTimeField(auto_now_add=True)  # set once on create
    updated_at = models.DateTimeField(auto_now=True)      # update on every save

    class Meta:
        # ✅ Prevent duplicate names of the same type per user (e.g., two 'Rent' Expenses for same user)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "type", "name"],
                name="uq_category_user_type_name",
            )
        ]
        ordering = ["type", "name"]  # neat default ordering in admin/lists
        verbose_name_plural = "Categories"

    def __str__(self):
        # ✅ Nice string for admin and shell
        return f"{self.name} ({self.type})"


class Transaction(models.Model):
    """
    A single money event (always a positive amount).
    - If type=Income, it contributes to Revenue.
    - If type=Expense, it contributes to Expenses.
    The P&L is computed as Total Income - Total Expenses.
    """

    # ✅ Each transaction belongs to a user (privacy boundary)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,                 # delete transactions if the user is removed
        related_name="transactions",
        help_text="Owner of this transaction",
    )

    # ✅ Short description, e.g., 'October Salary', 'Weekly Groceries'
    title = models.CharField(
        max_length=100,
        help_text="Short description, e.g., 'October Salary' or 'Groceries'",
    )

    # ✅ Always store positive amounts (use Decimal for money)
    amount = models.DecimalField(
        max_digits=12,                            # allows up to 999,999,999.99
        decimal_places=2,                         # 2 decimal places for currency
        validators=[MinValueValidator(Decimal("0.01"))],  # must be > 0
        help_text="Positive amount (e.g., 250.00)",
    )

    # ✅ Transaction type: 'Income' or 'Expense'
    transaction_type = models.CharField(
        max_length=7,
        choices=TRANSACTION_TYPES,
        help_text="Is this an Income or an Expense?",
    )

    # ✅ Link to a Category of the SAME type and SAME user
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,                 # ⚠️ PROTECT: you cannot delete a category with transactions
        related_name="transactions",
        help_text="Pick a category that matches the transaction type",
    )

    # ✅ When it happened; defaults to 'today' (you can edit it on the form)
    date = models.DateField(
        default=timezone.now,                     # uses your TIME_ZONE for display
        help_text="When did this happen?",
    )

    # ✅ Optional free text (notes, receipt refs, etc.)
    notes = models.TextField(
        blank=True,
        help_text="Optional notes (e.g., receipt ID, details)",
    )

    # ✅ Created/updated timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]              # newest first in lists

    def __str__(self):
        # ✅ Show title + signed amount in admin lists
        return f"{self.title} • {self.transaction_type} • {self.amount}"

    # ✅ Business rules to keep data consistent
    def clean(self):
        """
        Enforce:
        - amount > 0 (already ensured by validator)
        - category.user == user (you can only use your own categories)
        - category.type == transaction_type (no mixing)
        """
        # Import here to avoid circular imports during model loading

       # ✅ SAFER cross-field validation
    def clean(self):
        """
        Enforce:
        - category must belong to the same user (when category is set)
        - category.type must match transaction_type (when both are set)
        NOTE: Do NOT dereference self.category if it's unset; check category_id first.
        """
        # 1) If no category is set yet, skip cross-checks.
        #    The form ensures either an existing category OR a new one will be provided.
        if self.category_id is None:
            return

        # 2) Now it's safe to access self.category
        if self.user_id and self.category.user_id != self.user_id:
            raise ValidationError("This category does not belong to you.")

        if self.transaction_type and self.category.type != self.transaction_type:
            raise ValidationError("Category type must match the transaction type (Income/Expense).")

    # ✅ Keep this, but it will now be safe because clean() won’t touch an unset category
    def save(self, *args, **kwargs):
        self.full_clean()  # runs clean() + field validators
        super().save(*args, **kwargs)


