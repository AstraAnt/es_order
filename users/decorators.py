from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .services import get_current_membership


def role_required(*role_names):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("users:login")

            membership = get_current_membership(request)
            if membership is None:
                messages.error(request, "Сначала выберите business unit.")
                return redirect("users:select_business_unit")

            if membership.role.name not in role_names:
                messages.error(request, "У вас нет прав для доступа к этому разделу.")
                return redirect("home")

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
