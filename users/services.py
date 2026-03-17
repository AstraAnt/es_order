from django.apps import apps
from django.conf import settings

from .models import UserBusinessUnitMembership


SESSION_BUSINESS_UNIT_ID = "current_business_unit_id"


def get_business_unit_model():
    model_label = getattr(settings, "BUSINESS_UNIT_MODEL", None)
    if not model_label:
        return None
    return apps.get_model(model_label)


def get_user_memberships(user):
    if not user.is_authenticated:
        return UserBusinessUnitMembership.objects.none()

    return (
        UserBusinessUnitMembership.objects
        .select_related("role", "user")
        .filter(user=user, is_active=True)
        .order_by("business_unit_id", "role__name")
    )


def get_available_business_units(user):
    """
    Возвращает список словарей:
    [
        {"id": 1, "label": "BU name"},
        ...
    ]
    """
    memberships = get_user_memberships(user)
    model = get_business_unit_model()

    if model is None:
        return []

    ids = sorted(set(membership.business_unit_id for membership in memberships))
    if not ids:
        return []

    objects_map = {
        obj.pk: obj
        for obj in model.objects.filter(pk__in=ids)
    }

    result = []
    for bu_id in ids:
        obj = objects_map.get(bu_id)
        if obj:
            result.append({
                "id": obj.pk,
                "label": str(obj),
                "object": obj,
            })

    return result


def set_current_business_unit(request, business_unit_id):
    request.session[SESSION_BUSINESS_UNIT_ID] = int(business_unit_id)
    request.session.modified = True


def clear_current_business_unit(request):
    request.session.pop(SESSION_BUSINESS_UNIT_ID, None)
    request.session.modified = True


def get_current_business_unit_id(request):
    return request.session.get(SESSION_BUSINESS_UNIT_ID)


def get_current_business_unit(request):
    business_unit_id = get_current_business_unit_id(request)
    if not business_unit_id:
        return None

    model = get_business_unit_model()
    if model is None:
        return None

    try:
        return model.objects.get(pk=business_unit_id)
    except model.DoesNotExist:
        return None


def get_current_membership(request):
    if not request.user.is_authenticated:
        return None

    business_unit_id = get_current_business_unit_id(request)
    if not business_unit_id:
        return None

    return (
        UserBusinessUnitMembership.objects
        .select_related("role", "user")
        .filter(
            user=request.user,
            business_unit_id=business_unit_id,
            is_active=True,
        )
        .order_by("id")
        .first()
    )


def user_has_access_to_business_unit(user, business_unit_id):
    if not user.is_authenticated:
        return False

    return UserBusinessUnitMembership.objects.filter(
        user=user,
        business_unit_id=business_unit_id,
        is_active=True,
    ).exists()