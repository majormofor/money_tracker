# accounts/views.py


from django.shortcuts import render, redirect                    # ✅ render/redirect
from django.contrib.auth import login, logout                   # ✅ auth helpers
from django.contrib.auth.decorators import login_required       # ✅ protect views
from django.views.decorators.http import require_POST           # ✅ POST-only decorator
from django.contrib import messages                             # ✅ flash messages
from .forms import SignupForm                                   # ✅ our signup form
from .models import UserProfile   
from .forms import SignupForm, CurrencyForm   # ← make sure CurrencyForm is imported

  # ... your existing code ...
def signup(request):
    """
    Show the signup form and create a new user.
    After successful signup, log the user in and send them to the home page.
    """
    if request.method == "POST":                     # if the browser is submitting the form
        form = SignupForm(request.POST)              # bind POST data to our form
        if form.is_valid():                          # check all fields/validation rules
            user = form.save()                       # create the new user
            login(request, user)                     # log the user in immediately
            return redirect("accounts:home")         # send them to the home page
    else:
        form = SignupForm()                          # if it's a GET request, show a blank form

    # Render the template with the form (blank or with errors)
    return render(request, "registration/signup.html", {"form": form})




@login_required
def home(request):
    # ... your existing code ...
    """
    A very simple landing page after login.
    Later we’ll replace this with your real Dashboard.
    """
    return render(request, "accounts/home.html")     # just render the template




@require_POST                                  # ✅ only allow POST (no GET) for logout
def logout_view(request):
    logout(request)                            # ✅ clear session
    messages.success(request, "You have been logged out.")  # ✅ feedback
    return redirect("accounts:login")          # ✅ back to login page

# currency change/edit

@login_required                                                # ← force login to access this page
def currency_settings(request):
    """Let a logged-in user change their preferred currency in one field."""
    # 🧾 get or create a profile for this user (safety if signal didn’t run)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        # 📝 bind POST data to the form, editing THIS user's profile
        form = CurrencyForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()                                        # 💾 write the currency to DB
            messages.success(request, "Currency updated.")     # ✅ nice feedback
            # 🔁 send them back to Transactions (or wherever you prefer)
            return redirect("finance:transaction_list")
    else:
        # 📃 initial GET: show the form with the current value pre-filled
        form = CurrencyForm(instance=profile)

    # 🎨 render the small settings page
    return render(request, "accounts/currency_settings.html", {"form": form})