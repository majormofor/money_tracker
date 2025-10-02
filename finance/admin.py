# finance/admin.py
# ✅ Register ONLY finance models here (Category, Transaction)

from django.contrib import admin                          # ← Django admin site
from .models import Category, Transaction                 # ← finance models only

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ("name", "type", "user")              # columns in the list
    list_filter   = ("type",)                             # sidebar filter
    search_fields = ("name", "user__username")            # search box

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ("date", "title", "transaction_type", "amount", "category", "user")
    list_filter   = ("transaction_type", "date", "category")
    search_fields = ("title", "notes", "user__username")
    date_hierarchy = "date"                               # nice date drill-down
