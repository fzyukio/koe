from koe.model_utils import get_or_error
from koe.models import Preference


__all__ = ["get_preference", "set_preference"]


def get_preference(request):
    user = request.user
    key = get_or_error(request.POST, "key")
    pref = Preference.objects.filter(user=user, key=key).first()
    if pref is None:
        return dict(origin="get_preference", success=True, warning=None, payload=None)

    return dict(origin="get_preference", success=True, warning=None, payload=pref.value)


def set_preference(request):
    user = request.user
    key = get_or_error(request.POST, "key")
    value = get_or_error(request.POST, "value")
    pref = Preference.objects.filter(user=user, key=key).first()
    if pref is None:
        pref = Preference(user=user, key=key, value=value)
        pref.save()

    if pref.value != value:
        pref.value = value
        pref.save()

    return dict(origin="set_preference", success=True, warning=None, payload=True)
