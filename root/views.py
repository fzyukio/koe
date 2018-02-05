import importlib
import json
from collections import OrderedDict

from django.db.utils import OperationalError
from django.http import HttpResponse
from django.http import HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from koe.models import *
from root.models import *

PY3 = sys.version_info[0] == 3
if PY3:
    import builtins
else:
    import __builtin__ as builtins

try:
    builtins.profile
except AttributeError:
    builtins.profile = lambda x: x


def get_attrs(objs, table, extras={}):
    """
    Returns values of the attributes of the objects according to the table config
    :param objs:
    :param table:
    :param extras:
    :return:
    """
    ids = get_bulk_id(objs)
    if 'getter' in table:
        getter = table['getter']
        rows = getter(objs, extras)
    else:
        attrs = {}
        rows = []
        for column in table['columns']:
            getter = column['getter']
            attr = column['slug']
            value = getter(objs, extras)
            attrs[attr] = value

        for id in ids:
            row = {'id': id}
            for attr in attrs:
                row[attr] = attrs[attr][id]
            rows.append(row)

    for column in table['columns']:
        attr = column['slug']
        editable = column['editable']
        attr_editable = '__{}_editable'.format(attr)
        if callable(editable):
            editabilities = editable(objs, extras)
        else:
            editabilities = {id: editable for id in ids}

        for row in rows:
            id = row['id']
            editability = editabilities[id]
            row[attr_editable] = editability

    return rows


with open('tables.json', 'r', encoding='utf-8') as f:
    tables = json.loads(''.join(f.readlines()))

    for table in tables.values():
        klass = globals()[table['class']]
        table['class'] = klass

        has_bulk_getter = 'getter' in table
        has_bulk_setter = 'setter' in table

        if has_bulk_getter:
            table['getter'] = getattr(klass, table['getter'])
        for column in table['columns']:
            slug = column['slug']
            _type = column['type']
            _type = ValueTypes.get_key_val_pairs()[_type]
            column['type'] = _type
            column['editor'] = ValueTypes.get_associated_value(_type, 'editor')
            column['filter'] = ValueTypes.get_associated_value(_type, 'filter_type')
            column['sortable'] = ValueTypes.get_associated_value(_type, 'sortable')
            column['cssClass'] = column.get('css_class', '')

            if 'has_total' not in column:
                column['has_total'] = False

            is_attribute = column.get('is_attribute', False)
            is_extra_attr = column.get('is_extra_attr', False)

            editable = column.get('editable', False)
            if editable not in [True, False]:
                editable = getattr(klass, 'get_{}'.format(editable))
            column['editable'] = editable

            if not has_bulk_getter:
                if is_attribute:
                    column['getter'] = klass.get_FIELD(slug)
                elif is_extra_attr:
                    column['getter'] = klass.get_EXTRA_FIELD(slug)
                else:
                    column['getter'] = getattr(klass, 'get_{}'.format(slug))

            if not has_bulk_setter:
                if is_attribute:
                    column['setter'] = klass.set_FIELD(slug)
                elif is_extra_attr:
                    column['setter'] = klass.set_EXTRA_FIELD(slug)
                elif editable:
                        column['setter'] = getattr(klass, 'set_{}'.format(slug))

            if is_extra_attr:
                try:
                    ExtraAttr.objects.get_or_create(klass=klass.__name__, type=_type, name=slug)
                except OperationalError as e:
                    pass

            if 'total_label' not in column:
                column['total_label'] = '-/-'

with open('actions.json', 'r', encoding='utf-8') as f:
    actions = json.loads(''.join(f.readlines()))
    for slug in actions:
        action = actions[slug]
        _type = action['type']
        _type = ValueTypes.get_key_val_pairs()[_type]

        action['type'] = _type
        action['val2str'] = value_setter[_type]
        action['str2val'] = value_getter[_type]


def get_grid_column_definition(request):
    user = request.user
    grid_type = request.POST['grid-type']
    coldefs = tables[grid_type]['columns']
    table = tables[grid_type]

    columns = []

    for column in table['columns']:
        slug = column['slug']
        name = column['name']
        editable = column['editable']
        total_label = column['total_label']
        editor = column['editor']
        has_total = column['has_total']
        sortable = column['sortable']
        filter = column['filter']
        css_class = column['cssClass']

        if callable(editable):
            editable = 'True'

        column = dict(id=slug, name=name, field=slug, editable=editable, editor=editor, filter=filter,
                           sortable=sortable, hasTotal=has_total, totalLabel=total_label, cssClass=css_class)

        if editable:
            column['cssClass'] += 'editable'

        columns.append(column)


    value_actions = {k:v for k,v in actions.items()}

    name_to_column = {x['id']: x for x in columns}

    for apk, action in value_actions.items():
        handler = values_grid_action_handlers[apk]
        name_to_column = handler(apk, action, grid_type, coldefs, user, name_to_column)

    columns = list(name_to_column.values())

    # Final column is for the actions
    action_pks = [x for x in value_actions]
    columns.append({'id': 'actions', 'field': 'actions', 'name': 'Actions', 'actions': action_pks, 'formatter': 'Action'})

    return HttpResponse(json.dumps(columns))


def get_grid_content(request):
    """
    Get the configuration of the specified table from tables.json
    Then return the data according to the table's getters
    :param request:
    :return:
    """
    today = datetime.date.today()
    now = datetime.datetime.now()
    extras = dict(today=today, now=now)
    grid_type = request.POST['grid-type']
    for key in request.POST:
        if key.startswith('__extra__'):
            extra_kw = key[len('__extra__'):]
            extras[extra_kw] = request.POST[key]

    table = tables[grid_type]

    klass = table['class']
    objs = klass.objects.all()
    rows = get_attrs(objs, table, extras)
    return HttpResponse(json.dumps(rows))


def change_property_bulk(request):
    grid_type = request.POST['grid-type']
    value = request.POST['value']
    field = request.POST['field']

    table = tables[grid_type]
    columns = table['columns']
    klass = table['class']
    ids = json.loads(request.POST.get('ids', '[]'))
    objs = klass.objects.filter(pk__in=ids)
    print(objs)

    for column in columns:
        attr = column['slug']
        if attr == field:
            setter = column['setter']
            setter(objs, value, {})

    return HttpResponse('ok')

def change_properties(request):
    """
    When the user changes a row on the table, we will save the new value to the database, then return the updated row
    together with the total row, so that the view can update the table.
    :param request:
    :return:
    """
    grid_row = json.loads(request.POST['property'])
    grid_type = request.POST['grid-type']

    table = tables[grid_type]
    columns = table['columns']
    klass = table['class']
    obj = klass.objects.get(pk=grid_row['id'])

    for column in columns:
        attr = column['slug']
        editable = column['editable']
        if editable and attr in grid_row:
            val = grid_row[attr]
            if 'setter' in column:
                setter = column['setter']
                setter([obj], val, {})

    return HttpResponse('ok')


def change_action_values(request):
    column_ids_actions_values = json.loads(request.POST.get('column-ids-action-values', None))
    grid_type = request.POST['grid-type']
    user = request.user

    for column in column_ids_actions_values.keys():
        actions_values = column_ids_actions_values[column]
        # column_prefixed = '{}__{}'.format(grid_type, column)

        for action in actions_values:
            value = actions_values[action]
            action_definition = actions[action]
            val2str = action_definition['val2str']
            value = val2str(value)

            assert value is not None, 'actions_values = {}'.format(json.dumps(actions_values))

            action_value = ColumnActionValue.objects.filter(user=user, action=action, column=column, table=grid_type).first()
            if action_value is None:
                action_value = ColumnActionValue()
                action_value.action = action
                action_value.column = column
                action_value.table = grid_type
                action_value.user = user
            action_value.value = val2str(value)
            action_value.save()
    return HttpResponse('ok')


def reorder_columns_handler(apk, action, grid_type, coldefs, user, name_to_column):
    column_values = ColumnActionValue.objects\
        .filter(user=user, action=apk, table=grid_type, column__in=[x['slug'] for x in coldefs])\
        .values_list('column', 'value')

    str2val = action['str2val']
    column_values = {k: str2val(v) for k,v in column_values}

    column_names = name_to_column.keys()


    def sort_(pk):
        return str2val(column_values.get(pk, '-999999'))

    column_names = sorted(column_names, key=sort_)

    name_to_column = OrderedDict((k, name_to_column[k]) for k in column_names)

    return name_to_column


def set_column_width_handler(apk, action, grid_type, coldefs, user, name_to_column):
    column_values = ColumnActionValue.objects \
        .filter(user=user, action=apk, table=grid_type, column__in=[x['slug'] for x in coldefs]) \
        .values_list('column', 'value')

    str2val = action['str2val']

    for column, value in column_values:
        name_to_column[column]['width'] = str2val(value)
    return name_to_column


values_grid_action_handlers = {
    'reorder-columns': reorder_columns_handler,
    'set-column-width': set_column_width_handler
}


def _save_table(klass, table, columns):
    for row in table:
        # Ignore row id #total, because this row is not an actual object
        if row['id'] == 'total': continue

        obj = klass.objects.get(pk=row['id'])
        for column in columns:
            attr = column['slug']
            editable = column['editable']
            if attr in row and editable:
                setter = column['setter']
                setter([obj], row[attr], {})

        if hasattr(obj, 'complete'):
            obj.complete = True
            obj.save()


@csrf_exempt
def fetch_data(request, *args, **kwargs):
    """
    All fetch requests end up here and then delegated to the appropriate function, based on the POST key `fetch-type`
    :param request: must specify a valid `fetch-type` in POST data, otherwise 404
    :return: AJAX content
    """
    fetch_type = kwargs['type']
    module = kwargs.get('module', None)
    func_name = fetch_type.replace('-', '_')
    if isinstance(fetch_type, str):
        if module is not None:
            func_name = module + '.' + func_name
        fetch_func = globals().get(func_name, None)
        if fetch_func:
            retval = fetch_func(request)
            if retval:
                return retval
    retval = render(request, "errors/404.html")
    return HttpResponseNotFound(retval)


@csrf_exempt
def send_data(request, *args, **kwargs):
    """
    All fetch requests end up here and then delegated to the appropriate function, based on the POST key `fetch-type`
    :param request: must specify a valid `fetch-type` in POST data, otherwise 404
    :return: AJAX content
    """
    data_type = kwargs['type']
    func_name = data_type.replace('-', '_')
    if isinstance(data_type, str):
        fetch_func = globals().get(func_name, None)
        if fetch_func:
            retval = fetch_func(request)
            if retval:
                return retval
    retval = render(request, "errors/404.html")
    return HttpResponseNotFound(retval)


def get_view(name):
    class View(TemplateView):
        template_name = name + '.html'

        def get_context_data(self, **kwargs):
            context = super(View, self).get_context_data(**kwargs)
            return context

    return View.as_view()


class IndexView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        dms = DistanceMatrix.objects.all().values_list('id', 'algorithm')
        dms = list(dms)
        context['dms'] = dms
        return context


def register_view(package, module):
    # module = __import__(name, globals(), locals())
    # globals()[name] = module
    imported_modules = importlib.import_module('{}.{}'.format(package, module)).__dict__
    importable_names = imported_modules['__all__']
    globals_dict = globals()

    for importable_name in importable_names:
        new_name = '{}.{}'.format(package, importable_name)
        imported_module = imported_modules[importable_name]
        globals_dict[new_name] = imported_module
