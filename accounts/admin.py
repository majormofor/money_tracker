# accounts/admin.py
# 🛠️ Admin integration for UserProfile.

from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "currency", "initial_balance")
    search_fields = ("user__username",)
