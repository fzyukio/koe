from django.conf import settings
from django.template.loader import render_to_string
from dotmap import DotMap

from koe.model_utils import get_user_databases, assert_permission, get_or_error, get_user_accessible_databases
from koe.models import DatabaseAssignment, DatabasePermission, Database, TemporaryDatabase
from root.models import User, ExtraAttrValue


__all__ = ['get_sidebar']


def populate_context(obj, context):
    page_name = getattr(obj, 'page_name', None)
    if page_name is None:
        page_name = obj.__class__.page_name

    user = obj.request.user
    gets = obj.request.GET

    for key, value in gets.items():
        if key.startswith('__'):
            context['external{}'.format(key)] = value
        elif key.startswith('_'):
            context['internal{}'.format(key)] = value
        else:
            context[key] = value

    current_database = get_user_databases(user)

    specified_db = None
    db_class = Database if current_database is None else current_database.__class__

    if 'database' in gets:
        specified_db = gets['database']
        db_class = Database
    elif 'tmpdb' in gets:
        specified_db = gets['tmpdb']
        db_class = TemporaryDatabase

    if specified_db and (current_database is None or specified_db != current_database.name):
        current_database = get_or_error(db_class, dict(name=specified_db))

        current_database_value = ExtraAttrValue.objects.filter(attr=settings.ATTRS.user.current_database,
                                                               owner_id=user.id, user=user).first()
        if current_database_value is None:
            current_database_value = ExtraAttrValue(attr=settings.ATTRS.user.current_database, owner_id=user.id,
                                                    user=user)
        current_database_value.value = '{}_{}'.format(db_class.__name__, current_database.id)
        current_database_value.save()

    if db_class == Database:
        db_assignment = assert_permission(user, current_database, DatabasePermission.VIEW)
    else:
        db_assignment = {'can_view': True}

    context['databases'] = get_user_accessible_databases(user)
    context['current_database'] = current_database
    context['db_assignment'] = db_assignment

    context['my_tmpdbs'] = TemporaryDatabase.objects.filter(user=user)
    # context['other_tmpdbs'] = TemporaryDatabase.objects.exclude(user=user)

    if db_class == Database:
        underlying_databases = [current_database]
    else:
        underlying_databases = current_database.get_databases()

    other_users = DatabaseAssignment.objects\
        .filter(database__in=underlying_databases, permission__gte=DatabasePermission.VIEW)\
        .values_list('user__id', flat=True)
    other_users = User.objects.filter(id__in=other_users)

    viewas = gets.get('viewas', user.username)
    viewas = get_or_error(User, dict(username=viewas))
    context['viewas'] = viewas
    context['other_users'] = other_users

    granularity = gets.get('granularity', 'label')
    context['granularity'] = granularity
    context['page'] = page_name


def get_sidebar(request):
    page = get_or_error(request.POST, 'page')
    context = dict(user=request.user, page=page)

    obj = DotMap(page_name=page, request=request)

    populate_context(obj, context)
    return render_to_string('sidebar/sidebar.html', context=context)
