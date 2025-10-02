# accounts/views.py


from django.shortcuts import render, redirect                    # ✅ render/redirect
from django.contrib.auth import login, logout                   # ✅ auth helpers
from django.contrib.auth.decorators import login_required       # ✅ protect views
from django.views.decorators.http import require_POST           # ✅ POST-only decorator
from django.contrib import messages                             # ✅ flash messages
from .forms import SignupForm                                   # ✅ our signup form

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