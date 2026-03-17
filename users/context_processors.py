from .services import (
    get_available_business_units,
    get_current_business_unit,
    get_current_membership,
)


def current_business_unit(request):
    if not request.user.is_authenticated:
        return {
            "current_business_unit": None,
            "current_membership": None,
            "available_business_units": [],
        }

    return {
        "current_business_unit": get_current_business_unit(request),
        "current_membership": get_current_membership(request),
        "available_business_units": get_available_business_units(request.user),
    }
