from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import LoginUserForm, SelectBusinessUnitForm
from .services import (
    clear_current_business_unit,
    get_available_business_units,
    get_current_business_unit,
    set_current_business_unit,
    user_has_access_to_business_unit,
)


class UserLoginView(LoginView):
    template_name = "users/login.html"
    authentication_form = LoginUserForm

    def get_success_url(self):
        return reverse("users:post_login")


@login_required
def post_login_redirect_view(request):
    business_units = get_available_business_units(request.user)

    if not business_units:
        clear_current_business_unit(request)
        messages.error(request, "У вас нет доступа ни к одному business unit.")
        return redirect("home")

    if len(business_units) == 1:
        set_current_business_unit(request, business_units[0]["id"])
        return redirect("home")

    current_business_unit = get_current_business_unit(request)
    if current_business_unit:
        return redirect("home")

    return redirect("users:select_business_unit")


@login_required
def select_business_unit_view(request):
    business_units = get_available_business_units(request.user)

    if not business_units:
        clear_current_business_unit(request)
        messages.error(request, "У вас нет доступных business unit.")
        return redirect("home")

    if request.method == "POST":
        form = SelectBusinessUnitForm(request.POST, business_units=business_units)
        if form.is_valid():
            business_unit_id = int(form.cleaned_data["business_unit_id"])

            if not user_has_access_to_business_unit(request.user, business_unit_id):
                messages.error(request, "Нет доступа к выбранному business unit.")
                return redirect("users:select_business_unit")

            set_current_business_unit(request, business_unit_id)
            messages.success(request, "Business unit выбран.")
            return redirect("home")
    else:
        form = SelectBusinessUnitForm(business_units=business_units)

    return render(
        request,
        "users/select_business_unit.html",
        {
            "form": form,
            "title": "Выбор business unit",
        }
    )


def logout_user(request):
    logout(request)
    return HttpResponseRedirect(reverse("users:login"))
