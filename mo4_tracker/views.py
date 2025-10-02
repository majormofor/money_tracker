
from django.shortcuts import render  # ✅ import render to return a template response

def page_not_found_view(request, exception):  # ✅ this function will handle 404 errors
    # ✅ render the custom 404 template and set HTTP status to 404
    return render(request, "404.html", status=404)