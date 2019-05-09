from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

from koe.models import Database, DatabaseAssignment
from root.models import User, ExtraAttrValue


@receiver(user_logged_in, sender=User)
def remove_expired_database_access(**kwargs):
    user = kwargs['user']
    now = timezone.now()
    expired = DatabaseAssignment.objects.filter(user=user, expiry__lte=now)
    expired_database_ids = list(expired.values_list('database__id', flat=True))
    expired.delete()
    current_database = ExtraAttrValue.objects.filter(attr=settings.ATTRS.user.current_database, owner_id=user.id,
                                                           user=user).first()

    if current_database is not None:
        db_class_name, current_database_id = current_database.value.split('_')
        if db_class_name == Database.__name__:
            current_database_id = int(current_database_id)
            if current_database_id in expired_database_ids:
                current_database.delete()
