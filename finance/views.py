# finance/views.py
# ─────────────────────────────────────────────────────────────────────────────
# ✅ All views for the Finance app live here.
#    This file includes:
#      • Helpers (date parsing, period iteration, labels, currency)
#      • Category views: list/create/update/delete
#      • Transaction views: list/create/update/delete
#      • P&L report view (+ CSV export)
#      • Dashboard view (weekly-first, also supports monthly)
# ─────────────────────────────────────────────────────────────────────────────

# ===== Standard library imports =============================================
from datetime import date, timedelta                       # 🗓️ work with dates + ranges
from decimal import Decimal                                # 💰 precise currency math
import csv                                                 # 📄 CSV writing for report export
from io import StringIO                                    # 🧪 in-memory text buffer for CSV

# ===== Django imports ========================================================
from django.contrib import messages                        # 🔔 flash messages for user feedback
from django.contrib.auth.mixins import LoginRequiredMixin  # 🔒 require login on class-based views
from django.db.models import Sum, Case, When, Value, DecimalField  # 🧮 aggregations
from django.db.models.deletion import ProtectedError       # 🛡️ catch FK-protected deletes
from django.http import HttpResponse                       # 🌐 return CSV/downloads
from django.shortcuts import redirect                      # 🔀 redirects after post actions
from django.urls import reverse, reverse_lazy              # 🔗 build URLs safely
from django.views import View                              # 🧱 base class for simple custom views
from django.views.generic import (                         # 📦 class-based views we’ll use
    ListView, CreateView, UpdateView, DeleteView, TemplateView
)

# ===== Local app imports =====================================================
from .models import Category, Transaction                  # 💾 your app models
from .forms import CategoryForm, TransactionForm           # 📝 forms (with “Other…” support)


# ─────────────────────────────────────────────────────────────────────────────
# 🔎 Helper: parse 'YYYY-MM-DD' to a date (returns None if missing/bad)
# ─────────────────────────────────────────────────────────────────────────────
def _parse_yyyymmdd(s):
    """Turn '2025-10-01' into a date object; return None if missing or invalid."""
    try:
        y, m, d = map(int, (s or "").split("-"))          # 👈 split "YYYY-MM-DD" into numbers
        return date(y, m, d)                               # ✅ build a date
    except Exception:                                      # ⛑️ bad/missing input → None
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 🧭 Helper: iterate anchors for the x-axis (WEEKLY / MONTHLY)
#   • weekly  → each Monday
#   • monthly → first day of each month
#   (We default to weekly if bucket is unknown.)
# ─────────────────────────────────────────────────────────────────────────────
def _iter_periods(start: date, end: date, bucket: str):
    """Yield anchor dates from start..end inclusive according to bucket (weekly/monthly)."""
    if start > end:                                        # ⛑️ ensure correct order
        start, end = end, start

    if bucket == "weekly":                                 # 📅 one point per week
        cur = start - timedelta(days=(start.isoweekday() - 1))  # ↩ align to Monday
        while cur <= end:
            yield cur                                      # 🔹 Monday anchor
            cur += timedelta(days=7)                       # ➕ move a week

    elif bucket == "monthly":                              # 📅 one point per month
        cur = start.replace(day=1)                         # ↩ align to month start
        while cur <= end:
            yield cur                                      # 🔹 first of month
            # ➕ jump to the first of next month
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1, day=1)
            else:
                cur = cur.replace(month=cur.month + 1, day=1)

    else:                                                  # ⛑️ fallback = weekly
        yield from _iter_periods(start, end, "weekly")


# ─────────────────────────────────────────────────────────────────────────────
# 🏷️ Helper: render labels as strings for Chart.js
#   • weekly  → "YYYY-Www" (ISO week)
#   • monthly → "YYYY-MM"
# ─────────────────────────────────────────────────────────────────────────────
def _label_for(anchor: date, bucket: str) -> str:
    if bucket == "weekly":                                 # 🏷️ ISO week label
        iso = anchor.isocalendar()                         # (year, week, weekday)
        return f"{iso.year}-W{iso.week:02d}"
    if bucket == "monthly":                                # 🏷️ year-month label
        return anchor.strftime("%Y-%m")
    return anchor.strftime("%Y-%m-%d")                     # (not used; safety)


# ─────────────────────────────────────────────────────────────────────────────
# 💷 Helper: user currency symbol
#   • Reads user.profile.currency (related_name="profile")
#   • Falls back gracefully if profile missing
# ─────────────────────────────────────────────────────────────────────────────
_CURRENCY_SYMBOLS = {
    "GBP": "£", "USD": "$", "EUR": "€", "NGN": "₦", "GHS": "₵",
    "KES": "KSh", "ZAR": "R", "INR": "₹", "CAD": "$", "AUD": "$",
    "JPY": "¥", "CNY": "¥",
}

def _currency_for(user) -> str:
    """Return the user's preferred currency symbol (default '£')."""
    if not getattr(user, "is_authenticated", False):       # ⛑️ anonymous safety
        return "£"
    # 🧠 try our related_name "profile"; also support "userprofile" if older code exists
    profile = getattr(user, "profile", None) or getattr(user, "userprofile", None)
    if profile and getattr(profile, "currency", None):
        code = profile.currency
    else:
        # 🛠️ auto-create a default profile if missing
        try:
            from accounts.models import UserProfile        # local import to avoid circular at import time
            profile, _ = UserProfile.objects.get_or_create(user=user)
            code = profile.currency
        except Exception:
            return "£"                                     # ⛑️ ultimate fallback
    return _CURRENCY_SYMBOLS.get(code, code)               # 🔤 map code→symbol (or show code)


# ─────────────────────────────────────────────────────────────────────────────
# 📋 CATEGORY VIEWS (CRUD)
# ─────────────────────────────────────────────────────────────────────────────

class CategoryListView(LoginRequiredMixin, ListView):
    """List all categories for the logged-in user (Income + Expense)."""
    model = Category                                        # 📄 which model to list
    template_name = "finance/category_list.html"            # 🖼️ template to render
    context_object_name = "categories"                      # 🔑 name for the queryset in template
    paginate_by = 50                                        # 📄 optional: paginate long lists

    def get_queryset(self):
        # 🔒 only this user's categories, ordered by type then name
        return (Category.objects
                .filter(user=self.request.user)
                .order_by("type", "name"))

class CategoryCreateView(LoginRequiredMixin, CreateView):
    """Create a new category; enforce uniqueness per (user, type, name) via form."""
    model = Category                                        # 🧱 create this model
    form_class = CategoryForm                               # 📝 our model form
    template_name = "finance/category_form.html"            # 🖼️ template
    success_url = reverse_lazy("finance:category_list")     # ✅ where to go after save

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()                  # 🔌 base kwargs
        kwargs["user"] = self.request.user                  # 👤 pass user into form for validation/saving
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user              # 👤 attach owner
        messages.success(self.request, "Category created.") # ✅ nice feedback
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing category (belongs to the user)."""
    model = Category                                        # 🧱 update this model
    form_class = CategoryForm                               # 📝 form with uniqueness checks
    template_name = "finance/category_form.html"            # 🖼️ reuse same form
    success_url = reverse_lazy("finance:category_list")     # ✅ back to list

    def get_queryset(self):
        # 🔒 only allow editing categories owned by this user
        return Category.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()                  # 🔌 base kwargs
        kwargs["user"] = self.request.user                  # 👤 pass user for clean_name
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Category updated.") # ✅ feedback
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a category (blocked if any Transaction references it)."""
    model = Category                                        # 🧱 delete from here
    template_name = "finance/category_confirm_delete.html"  # 🖼️ confirmation page
    success_url = reverse_lazy("finance:category_list")     # ✅ back to list

    def get_queryset(self):
        # 🔒 restrict delete to user's own categories
        return Category.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        # 🔒 extra guard: ensure object belongs to user before handling
        self.object = self.get_object()
        try:
            response = super().post(request, *args, **kwargs)   # 🗑️ attempt delete
            messages.success(request, "Category deleted.")       # ✅ success
            return response
        except ProtectedError:
            # 🛡️ FK-protected: tell user how to resolve
            messages.error(
                request,
                "You can’t delete this category because it has transactions. "
                "Delete or reassign those transactions first."
            )
            return redirect(self.success_url)                    # 🔁 back to list


# ─────────────────────────────────────────────────────────────────────────────
# 🔧 Small helper: build JS-friendly category lists for the form
#     (used by Transaction form to filter by Income/Expense client-side)
# ─────────────────────────────────────────────────────────────────────────────
def _user_categories_json(user):
    """Return two lists of dicts: income + expense categories [{id, name}, ...]."""
    income = list(Category.objects.filter(user=user, type="Income")
                  .order_by("name").values("id", "name"))
    expense = list(Category.objects.filter(user=user, type="Expense")
                   .order_by("name").values("id", "name"))
    return income, expense


# ─────────────────────────────────────────────────────────────────────────────
# 💳 TRANSACTION VIEWS (CRUD)
# ─────────────────────────────────────────────────────────────────────────────

class TransactionListView(LoginRequiredMixin, ListView):
    """
    🧾 Transactions page with:
      - GET filters (type/category/date range/search)
      - Correct KPI totals for the *filtered* queryset
      - Context keys that your template expects: total_income, total_expense, net,
        currency, filters (echo), all_categories.
    """
    model = Transaction
    template_name = "finance/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 50  # tweak as you like

    # ---- Small helper: read and normalize all filters from the query string ----
    def _filters(self):
        """
        Return a dict of filter values as strings (or empty string if missing) so
        the template can echo them back into the form controls.
        """
        GET = self.request.GET
        return {
            "type": (GET.get("type") or "Both"),                 # "Both" | "Income" | "Expense"
            "category": (GET.get("category") or ""),             # category id as string or ""
            "date_from": (GET.get("date_from") or ""),           # "YYYY-MM-DD" or ""
            "date_to": (GET.get("date_to") or ""),               # "YYYY-MM-DD" or ""
            "q": (GET.get("q") or ""),                           # search text
        }

    # ---- Apply filters to the base queryset shown in the table ----
    def get_queryset(self):
        """
        Build the filtered queryset that powers the table (and KPIs).
        We also stash it on self so get_context_data can reuse it.
        """
        f = self._filters()  # read current filters

        # Start from this user's transactions, newest first, and prefetch category
        qs = (Transaction.objects
              .filter(user=self.request.user)
              .select_related("category")
              .order_by("-date", "-id"))

        # 1) Type filter
        t = f["type"]
        if t in ("Income", "Expense"):                           # ignore "Both"
            qs = qs.filter(transaction_type=t)

        # 2) Category filter
        if f["category"]:
            try:
                qs = qs.filter(category_id=int(f["category"]))    # safe int cast
            except ValueError:
                pass  # bad id in URL → just ignore category filter

        # 3) Date range filter
        if f["date_from"]:
            df = _parse_yyyymmdd(f["date_from"])                  # convert "YYYY-MM-DD" → date or None
            if df:
                qs = qs.filter(date__gte=df)
        if f["date_to"]:
            dt = _parse_yyyymmdd(f["date_to"])
            if dt:
                qs = qs.filter(date__lte=dt)

        # 4) Search filter (title OR notes contains)
        if f["q"]:
            from django.db.models import Q                        # import here to avoid top clutter
            qs = qs.filter(Q(title__icontains=f["q"]) | Q(notes__icontains=f["q"]))

        # keep the filtered queryset for KPI calculations in get_context_data
        self._filtered_qs = qs
        return qs

    # ---- Build page context exactly as the template expects ----
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Reuse the filtered queryset (or build it if missing)
        qs = getattr(self, "_filtered_qs", None) or self.get_queryset()

        # KPI totals for the *filtered* set
        totals = qs.aggregate(
            income_total=Sum(
                Case(
                    When(transaction_type="Income", then="amount"),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            expense_total=Sum(
                Case(
                    When(transaction_type="Expense", then="amount"),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
        )
        income_total = totals["income_total"] or Decimal("0")
        expense_total = totals["expense_total"] or Decimal("0")

        # Currency symbol for display (e.g., £, ₦, $, €)
        ctx["currency"] = _currency_for(self.request.user)

        # Names that your template uses
        ctx["total_income"] = income_total
        ctx["total_expense"] = expense_total
        ctx["net"] = income_total - expense_total

        # All categories for the filter dropdown (id, name, type) for this user
        ctx["all_categories"] = list(
            Category.objects
            .filter(user=self.request.user)
            .order_by("type", "name")
            .values("id", "name", "type")
        )

        # Echo the filters back so the form keeps its selections
        ctx["filters"] = self._filters()

        return ctx
class TransactionCreateView(LoginRequiredMixin, CreateView):
    """Add a transaction. Form supports 'Other…' to create a new category on the fly."""
    model = Transaction                                     # 🧱 create this model
    form_class = TransactionForm                            # 📝 our smart form
    template_name = "finance/transaction_form.html"         # 🖼️ template
    success_url = reverse_lazy("finance:transaction_list")  # ✅ back to list on save

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()                  # 🔌 base kwargs
        kwargs["user"] = self.request.user                  # 👤 pass user → filtering + auto-create category
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)            # 🔌 base context
        income, expense = _user_categories_json(self.request.user)  # 📦 lists for client-side filtering
        ctx["income_categories"] = income                   # 🔹 used by template json_script
        ctx["expense_categories"] = expense                 # 🔹 used by template json_script
        return ctx

    def form_valid(self, form):
        form.instance.user = self.request.user              # 👤 attach owner
        messages.success(self.request, "Transaction saved.")# ✅ feedback
        return super().form_valid(form)

class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    """Edit a transaction. Same form logic as create."""
    model = Transaction                                     # 🧱 update this model
    form_class = TransactionForm                            # 📝 form (filters by user/type)
    template_name = "finance/transaction_form.html"         # 🖼️ template
    success_url = reverse_lazy("finance:transaction_list")  # ✅ back to list

    def get_queryset(self):
        # 🔒 only allow editing user's own transactions
        return Transaction.objects.filter(user=self.request.user).select_related("category")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()                  # 🔌 base kwargs
        kwargs["user"] = self.request.user                  # 👤 pass user into form
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)            # 🔌 base context
        income, expense = _user_categories_json(self.request.user)  # 📦 lists for select
        ctx["income_categories"] = income
        ctx["expense_categories"] = expense
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Transaction updated.")  # ✅ feedback
        return super().form_valid(form)

class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a transaction (simple)."""
    model = Transaction                                     # 🧱 delete from here
    template_name = "finance/transaction_confirm_delete.html"  # 🖼️ confirmation page
    success_url = reverse_lazy("finance:transaction_list")  # ✅ back to list

    def get_queryset(self):
        # 🔒 only user's own transactions
        return Transaction.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Transaction deleted.")   # ✅ feedback
        return super().post(request, *args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# 📑 PROFIT & LOSS REPORT VIEW (+ CSV EXPORT)
# ─────────────────────────────────────────────────────────────────────────────

class PlReportView(LoginRequiredMixin, TemplateView):
    """Shows P&L for a selected window + breakdown by category."""
    template_name = "finance/report_pl.html"               # 🖼️ template to render

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)            # 🔌 base context

        # 📅 read window (defaults: last 30 days for reports)
        date_to = _parse_yyyymmdd(self.request.GET.get("date_to")) or date.today()
        date_from = _parse_yyyymmdd(self.request.GET.get("date_from")) or (date_to - timedelta(days=29))

        # 🔍 base queryset (user + date range)
        qs = (Transaction.objects
              .filter(user=self.request.user, date__gte=date_from, date__lte=date_to)
              .select_related("category"))

        # 🧮 totals (window)
        totals = qs.aggregate(
            income_total=Sum(
                Case(When(transaction_type="Income", then="amount"),
                     default=Value(0),
                     output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
            expense_total=Sum(
                Case(When(transaction_type="Expense", then="amount"),
                     default=Value(0),
                     output_field=DecimalField(max_digits=12, decimal_places=2))
            ),
        )
        income_total = totals["income_total"] or Decimal("0.00")   # 💰 window income
        expense_total = totals["expense_total"] or Decimal("0.00") # 💸 window expense
        net_total = income_total - expense_total                   # 🧮 net

        # 🧩 breakdown by category (separate for Income/Expense)
        income_by_cat = (qs.filter(transaction_type="Income")
                         .values("category__name")
                         .annotate(total=Sum("amount"))
                         .order_by("-total"))
        expense_by_cat = (qs.filter(transaction_type="Expense")
                          .values("category__name")
                          .annotate(total=Sum("amount"))
                          .order_by("-total"))

        # 📤 context to template
        ctx.update({
            "currency": _currency_for(self.request.user),          # 💱 symbol
            "date_from": date_from.strftime("%Y-%m-%d"),           # 📅 bind to inputs
            "date_to": date_to.strftime("%Y-%m-%d"),
            "income_total": income_total,                          # 🔢 totals
            "expense_total": expense_total,
            "net_total": net_total,
            "income_by_cat": income_by_cat,                        # 📊 lists of dicts
            "expense_by_cat": expense_by_cat,
        })
        return ctx

class PlCsvExportView(LoginRequiredMixin, View):
    """Return a CSV export of transactions for the selected window."""
    def get(self, request, *args, **kwargs):
        # 📅 read window (same defaults as report)
        date_to = _parse_yyyymmdd(request.GET.get("date_to")) or date.today()
        date_from = _parse_yyyymmdd(request.GET.get("date_from")) or (date_to - timedelta(days=29))

        # 🔍 pull rows (user + window)
        qs = (Transaction.objects
              .filter(user=request.user, date__gte=date_from, date__lte=date_to)
              .select_related("category")
              .order_by("date", "transaction_type", "id"))

        # 🧪 write CSV into memory
        buffer = StringIO()                                      # 🧰 in-memory text buffer
        writer = csv.writer(buffer)                              # ✍️ CSV writer

        # 🧾 header row
        writer.writerow(["Date", "Type", "Category", "Title", "Amount", "Notes"])

        # 🧾 data rows
        for tx in qs:
            writer.writerow([
                tx.date.strftime("%Y-%m-%d"),                   # 📅 date
                tx.transaction_type,                            # 💳 Income/Expense
                getattr(tx.category, "name", "") or "",         # 🏷️ category name (or blank)
                tx.title,                                       # 📝 description
                f"{tx.amount:.2f}",                             # 💰 amount with 2dp
                (tx.notes or "").replace("\n", " ").strip(),    # 🗒️ notes (single line)
            ])

        # 📦 build HTTP response for download
        filename = f"pl_export_{date_from:%Y%m%d}_{date_to:%Y%m%d}.csv"  # 📛 nice filename
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")  # 📤 CSV content
        response["Content-Disposition"] = f'attachment; filename="{filename}"'  # 💾 download hint
        return response


# ─────────────────────────────────────────────────────────────────────────────
# 📊 DASHBOARD VIEW (weekly-first; optional monthly)
#   • Densifies the timeline so lines span the whole period.
#   • Aggregates in Python (date-safe across DB backends).
#   • Produces three series: Income, Expense, Net.
#   • Donut shows expense by category; template shows % + center total.
# ─────────────────────────────────────────────────────────────────────────────

class DashboardView(LoginRequiredMixin, TemplateView):
    """Weekly-first dashboard with KPIs, line chart (Income/Expense/Net), donut (Expense by category)."""
    template_name = "finance/dashboard.html"                 # 🖼️ template to render

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)             # 🔌 base context

        # 1) 📅 Date range (default ≈ last 90 days → ~13 weeks)
        date_to = _parse_yyyymmdd(self.request.GET.get("date_to")) or date.today()
        date_from = _parse_yyyymmdd(self.request.GET.get("date_from")) or (date_to - timedelta(days=89))

        # 2) 🪜 Granularity: weekly (default) or monthly
        bucket = (self.request.GET.get("bucket") or "weekly").lower()
        if bucket not in {"weekly", "monthly"}:              # ⛑️ enforce supported values
            bucket = "weekly"

        # 3) 🔍 Base queryset (user + window)
        qs = Transaction.objects.filter(user=self.request.user,
                                        date__gte=date_from,
                                        date__lte=date_to)

        # 4) 🧮 KPIs over the window
        totals = qs.values("transaction_type").annotate(total=Sum("amount"))  # ↯ group by type
        income_total = sum((r["total"] for r in totals if r["transaction_type"] == "Income"), Decimal("0"))
        expense_total = sum((r["total"] for r in totals if r["transaction_type"] == "Expense"), Decimal("0"))
        net_total = (income_total or Decimal("0")) - (expense_total or Decimal("0"))

        # 5) 📦 Aggregate by bucket (Python-anchored to avoid date/datetime mismatches)
        def _anchor_for(d: date) -> date:
            # 🔹 weekly → Monday; monthly → day 1
            if bucket == "weekly":
                return d - timedelta(days=(d.isoweekday() - 1))
            if bucket == "monthly":
                return d.replace(day=1)
            return d

        rows = (qs.values("date", "transaction_type")        # 🔎 minimal columns from DB
                 .annotate(total=Sum("amount"))              # 🧮 sum per day + type
                 .order_by("date"))                          # 📅 ascending dates

        bucket_map = {}                                      # 🗺️ {anchor_date: (inc_dec, exp_dec)}
        for r in rows:
            anchor = _anchor_for(r["date"])                  # 🎯 normalize date → anchor
            inc, exp = bucket_map.get(anchor, (Decimal("0"), Decimal("0")))
            if r["transaction_type"] == "Income":
                inc += r["total"] or Decimal("0")
            else:
                exp += r["total"] or Decimal("0")
            bucket_map[anchor] = (inc, exp)                  # 💾 store per-anchor totals

        # 6) 🧱 Densify timeline + build line series in label order
        labels, line_income, line_expense, line_net = [], [], [], []
        for anchor in _iter_periods(date_from, date_to, bucket):
            labels.append(_label_for(anchor, bucket))        # 🏷️ string label
            inc_dec, exp_dec = bucket_map.get(anchor, (Decimal("0"), Decimal("0")))
            inc, exp = float(inc_dec), float(exp_dec)        # 🔢 convert for Chart.js
            line_income.append(inc)
            line_expense.append(exp)
            line_net.append(inc - exp)

        # 7) 🍩 Donut: expense by category (window)
        expense_by_cat = (qs.filter(transaction_type="Expense")
                           .values("category__name")
                           .annotate(total=Sum("amount"))
                           .order_by("-total"))
        pie_labels = [row["category__name"] or "Uncategorised" for row in expense_by_cat]
        pie_values = [float(row["total"] or 0) for row in expense_by_cat]

        # 8) 📤 Context → template
        ctx.update({
            "currency": _currency_for(self.request.user),    # 💱 symbol for KPIs/tooltips/center text
            "date_from": date_from.strftime("%Y-%m-%d"),     # 📅 bind inputs
            "date_to": date_to.strftime("%Y-%m-%d"),
            "bucket": bucket,                                # 🪜 remember current granularity

            "kpi_income": income_total,                      # 🔢 KPI totals
            "kpi_expense": expense_total,
            "kpi_net": net_total,

            "line_labels": labels,                           # 📈 x-axis labels
            "line_income": line_income,                      # 📈 y-series
            "line_expense": line_expense,
            "line_net": line_net,

            "pie_labels": pie_labels,                        # 🍩 donut labels/values
            "pie_values": pie_values,
        })
        return ctx
