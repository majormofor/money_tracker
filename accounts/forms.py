# accounts/forms.py
# ✅ Signup form that asks for username, email, password, and preferred currency.

from django import forms                              # build HTML forms safely
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import UserProfile, CURRENCY_CHOICES     # currency list + profile model

User = get_user_model()                               # supports custom User if you add one later


class SignupForm(UserCreationForm):
    # 📧 Optional email (nice to have)
    email = forms.EmailField(required=False, label="Email (optional)")

    # 💱 Our new field (this is what your template tries to render)
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,                     # e.g. GBP, USD, EUR, ₦...
        label="Preferred currency",
        help_text="Used to display totals and charts.",
    )

    class Meta:
        model = User
        # 🧩 IMPORTANT: include 'currency' here so Django binds/validates it
        fields = ["username", "email", "password1", "password2", "currency"]

    def save(self, commit=True):
        """
        💾 Create the User first, then create/update the matching UserProfile
        with the selected currency so dashboards use it immediately.
        """
        user = super().save(commit=commit)            # creates the new user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.currency = self.cleaned_data.get("currency") or profile.currency
        if commit:
            profile.save()
        return user
