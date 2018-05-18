from django.db.models.signals import post_save
from django.dispatch import receiver

from koe.models import DatabasePermission, Database, DatabaseAssignment
from root.models import User

invitation_code_privileges = {
    'KOELAB-PN': {
        'database': 'Koe Lab',
        'permission': DatabasePermission.ANNOTATE
    }
}


@receiver(post_save, sender=User)
def user_creation_handler(sender, **kwargs):
    """
    Grant user access to specific database if they use invitation code
    :param sender:
    :param kwargs:
    :return:
    """
    user = kwargs['instance']
    created = kwargs['created']
    raw = kwargs['raw']

    if not created or raw:
        return

    invitation_code = user.invitation_code.code
    if invitation_code in invitation_code_privileges:
        privilege = invitation_code_privileges[invitation_code]
        database = Database.objects.filter(name=privilege['database']).first()
        permission = privilege['permission']

        if database:
            DatabaseAssignment.objects.create(user=user, database=database, permission=permission)
