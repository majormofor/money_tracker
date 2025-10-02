# accounts/models.py
# 🧱 Models for the accounts app: we store per-user preferences (currency, etc.)

from decimal import Decimal                                          # ✅ precise money
from django.conf import settings                                     # ✅ reference AUTH_USER_MODEL safely
from django.core.validators import MinValueValidator                 # ✅ validate non-negative numbers
from django.db import models                                         # ✅ base ORM

# ✅ Central list of currencies (ISO code → label); used by forms & admin
CURRENCY_CHOICES = [
    ("GBP", "British Pound (£)"),
    ("USD", "US Dollar ($)"),
    ("EUR", "Euro (€)"),
    ("NGN", "Nigerian Naira (₦)"),
    ("GHS", "Ghanaian Cedi (₵)"),
    ("KES", "Kenyan Shilling (KSh)"),
    ("ZAR", "South African Rand (R)"),
    ("INR", "Indian Rupee (₹)"),
    ("CAD", "Canadian Dollar ($)"),
    ("AUD", "Australian Dollar ($)"),
    ("JPY", "Japanese Yen (¥)"),
]

class UserProfile(models.Model):
    """
    📄 One profile per user.
    - currency: how we display money
    - initial_balance: optional starting figure for summaries
    """

    # 🔗 link to the user (AUTH_USER_MODEL allows custom User later)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,           # ✅ delete profile if user is deleted
        related_name="profile",             # ✅ access via user.profile
        help_text="The user this profile belongs to",
    )

    # 💱 preferred currency code (e.g. GBP, USD)
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,           # ✅ show nice labels in forms
        default="GBP",
        help_text="3-letter currency code, e.g., GBP, USD, EUR",
    )

    # 🧾 optional starting balance for reports
    initial_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Starting balance (optional), used in summaries",
    )

    def __str__(self):
        return f"Profile for {self.user}"
