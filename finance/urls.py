# finance/urls.py
# ✅ URL routes for the Finance app.
#    Every line is commented so it’s easy to follow.

from django.urls import path                   # 🔗 path() maps URL patterns to views
from . import views                            # 📦 import our class-based views from finance/views.py

# 🏷️ Namespace for reverse() and {% url %} lookups: use 'finance:route_name'
app_name = "finance"

# 🗺️ All routes for dashboard, categories, transactions, and reports.
urlpatterns = [
    # ───────────── Dashboard ─────────────
    path(
        "dashboard/",                          # 🌐 /dashboard/
        views.DashboardView.as_view(),         # 👀 class-based view → as_view()
        name="dashboard",                      # 🔑 {% url 'finance:dashboard' %}
    ),

    # ───────────── Categories (CRUD) ─────────────
    path(
        "categories/",                         # 🌐 /categories/
        views.CategoryListView.as_view(),      # 📄 list all categories (user-scoped)
        name="category_list",
    ),
    path(
        "categories/add/",                     # 🌐 /categories/add/
        views.CategoryCreateView.as_view(),    # ➕ create a category
        name="category_create",
    ),
    path(
        "categories/<int:pk>/edit/",           # 🌐 /categories/12/edit/
        views.CategoryUpdateView.as_view(),    # ✏️ update a category
        name="category_edit",
    ),
    path(
        "categories/<int:pk>/delete/",         # 🌐 /categories/12/delete/
        views.CategoryDeleteView.as_view(),    # 🗑️ delete a category (protected if in use)
        name="category_delete",
    ),

    # ───────────── Transactions (CRUD) ─────────────
    path(
        "transactions/",                       # 🌐 /transactions/
        views.TransactionListView.as_view(),   # 📄 list transactions
        name="transaction_list",
    ),
    path(
        "transactions/add/",                   # 🌐 /transactions/add/
        views.TransactionCreateView.as_view(), # ➕ add a transaction (supports “Other…” category)
        name="transaction_create",
    ),
    path(
        "transactions/<int:pk>/edit/",         # 🌐 /transactions/34/edit/
        views.TransactionUpdateView.as_view(), # ✏️ edit transaction
        name="transaction_update",
    ),
    path(
        "transactions/<int:pk>/delete/",       # 🌐 /transactions/34/delete/
        views.TransactionDeleteView.as_view(), # 🗑️ delete transaction
        name="transaction_delete",
    ),

    # ───────────── Reports (P&L + CSV export) ─────────────
    path(
        "reports/pl/",                         # 🌐 /reports/pl/
        views.PlReportView.as_view(),          # ✅ P&L page (NOTE: PlReportView, not PLReportView)
        name="pl_report",
    ),
    path(
        "reports/pl/export.csv",               # 🌐 /reports/pl/export.csv
        views.PlCsvExportView.as_view(),       # 📥 CSV download for current filter window
        name="pl_export_csv",
    ),
]
