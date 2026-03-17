from django.shortcuts import redirect

from .services import get_current_business_unit


class CurrentBusinessUnitRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and get_current_business_unit(request) is None:
            return redirect("users:select_business_unit")
        return super().dispatch(request, *args, **kwargs)
