# accounts/forms.py
# ✅ Signup form that asks for username, email, password, and preferred currency.

from django import forms                              # build HTML forms safely
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import UserProfile, CURRENCY_CHOICES     # currency list + profile model
from django.forms import ModelForm                         # ← helper to build forms from models

User = get_user_model()                               # supports custom User if you add one later

class SignupForm(UserCreationForm):
    """
    ✅ Our signup form:
       - Requires a unique email (clean_email)
       - Captures preferred currency and saves it on the user's profile
    """

    # 📧 Make email REQUIRED and explain why
    email = forms.EmailField(
        required=True,                                     # ← force users to provide an email
        label="Email",
        help_text="Used for password resets. Must be unique.",  # ← clarity for users
    )

    # 💱 Let the user pick a preferred currency at signup
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,                          # ← e.g., GBP, USD, EUR, NGN…
        label="Preferred currency",
        help_text="Used to display totals and charts.",
        initial="GBP",                                     # ← set any default you like
    )

    class Meta(UserCreationForm.Meta):
        model = User                                       # ← the auth user model
        # 🧩 Include currency so Django binds/validates it with the rest of the form
        fields = ("username", "email", "password1", "password2", "currency")

    def clean_email(self):
        """
        ✅ Enforce UNIQUE email (case-insensitive).
           - Strips whitespace
           - Blocks duplicates before creating the user
        """
        # 🧼 Normalize input
        email = (self.cleaned_data.get("email") or "").strip()

        # 🔎 Guard: still required (double safety in case required=True is bypassed)
        if not email:
            raise forms.ValidationError("Email is required.")

        # 🚫 Check for duplicates (case-insensitive)
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        # ✅ Looks good
        return email

    def save(self, commit=True):
        """
        💾 Create the User, attach email, then store currency in the UserProfile.
        """
        # 🛠️ Build the user instance without saving yet so we can set .email first
        user = super().save(commit=False)

        # 📧 copy validated email onto the user model
        user.email = self.cleaned_data["email"]

        # 💾 Save the user if requested (normal path)
        if commit:
            user.save()

        # 👤 Ensure a profile exists for this user, then store currency preference
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.currency = self.cleaned_data.get("currency") or profile.currency

        # 💾 Save the profile if requested
        if commit:
            profile.save()

        # ↩️ Return the new user instance for the view to log in/redirect
        return user
    
    

class CurrencyForm(ModelForm):
    """A tiny form that edits only the 'currency' field on the user's profile."""

    class Meta:
        model = UserProfile                                # ← we are editing the UserProfile table
        fields = ["currency"]                              # ← only expose the 'currency' field to the form

    def __init__(self, *args, **kwargs):
        # 👇 call the parent constructor first (this builds the default fields)
        super().__init__(*args, **kwargs)
        # 🔒 ensure choices come from the central list so users can’t submit random codes
        self.fields["currency"].choices = CURRENCY_CHOICES
        # 🏷️ nice label + help text (optional, improves UX)
        self.fields["currency"].label = "Preferred currency"
        self.fields["currency"].help_text = "Used to display totals, KPIs and charts."
