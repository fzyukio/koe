import datetime
import importlib
import json
from collections import OrderedDict
from json import JSONEncoder
import sys

from django.db.models.base import ModelBase
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpResponse
from django.http import HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from koe import jsons
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


JSONEncoder_olddefault = JSONEncoder.default


def JSONEncoder_newdefault(self, obj):
    """
    The original JSONEncoder doesn't handle datetime object.
    Replace it with this
    :param self:
    :param obj:
    :return: the JSONified string
    """
    if isinstance(obj, datetime.datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    return JSONEncoder_olddefault(self, obj)


JSONEncoder.default = JSONEncoder_newdefault


tables = None
actions = None


def get_attrs(objs, table, extras):
    """
    Returns values of the attributes of the objects according to the table config
    :param objs: a list of ModelBase objects
    :param table: the table to display
    :param extras: some getters need extra information
    :return: all the rows to be displayed.
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


def init_tables():
    """
    Modify the raw table config in jsons to make the items (getters/setters) directly usable as Python object
    :return: None
    """
    global tables, actions
    global_namespace = globals()

    tables = jsons.tables
    for table in tables.values():
        klass = global_namespace[table['class']]
        table['class'] = klass

        has_bulk_getter = 'getter' in table
        has_bulk_setter = 'setter' in table

        if has_bulk_getter:
            table['getter'] = global_namespace[table['getter']]
        for column in table['columns']:
            slug = column['slug']
            _type = column['type']
            _type = ValueTypes.get_key_val_pairs()[_type]
            column['type'] = _type
            column['editor'] = column.get('editor', ValueTypes.get_associated_value(_type, 'editor'))
            column['formatter'] = column.get('formatter', ValueTypes.get_associated_value(_type, 'formatter'))
            column['filter'] = ValueTypes.get_associated_value(_type, 'filter_type')
            column['sortable'] = ValueTypes.get_associated_value(_type, 'sortable')
            column['copyable'] = ValueTypes.get_associated_value(_type, 'copyable')
            column['exportable'] = ValueTypes.get_associated_value(_type, 'exportable')
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
                except (OperationalError, ProgrammingError) as e:
                    pass

            if 'total_label' not in column:
                column['total_label'] = '-/-'

    actions = jsons.actions
    for slug in actions:
        action = actions[slug]
        _type = action['type']
        _type = ValueTypes.get_key_val_pairs()[_type]

        action['type'] = _type
        action['val2str'] = value_setter[_type]
        action['str2val'] = value_getter[_type]


def get_grid_column_definition(request):
    """
    Return slickgrid's array of column definitions
    :param request: must specify grid-type
    :return:
    """
    user = request.user
    table_name = request.POST['grid-type']
    table = tables[table_name]

    columns = []

    for column in table['columns']:
        slug = column['slug']
        name = column['name']
        editable = column['editable']
        total_label = column['total_label']
        editor = column['editor']
        formatter = column['formatter']
        has_total = column['has_total']
        sortable = column['sortable']
        filter = column['filter']
        css_class = column['cssClass']
        copyable = column['copyable']
        exportable = column['exportable']

        if callable(editable):
            editable = 'True'

        column = dict(id=slug, name=name, field=slug, editable=editable, editor=editor, filter=filter,
                      formatter=formatter, sortable=sortable, hasTotal=has_total, totalLabel=total_label,
                      cssClass=css_class, copyable=copyable, exportable=exportable)

        if editable:
            column['cssClass'] += ' editable'

        columns.append(column)

    name_to_column = {x['id']: x for x in columns}
    action_names = list(actions.keys())

    for action_name in action_names:
        handler = values_grid_action_handlers[action_name]
        name_to_column = handler(action_name, table_name, user, name_to_column)

    columns = list(name_to_column.values())

    # Final column is for the actions
    columns.append({'id': 'actions', 'field': 'actions', 'name': 'Actions', 'actions': action_names,
                    'formatter': 'Action'})

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
    extras = dict(today=today, now=now, user=request.user)
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


def set_property_bulk(request):
    """
    Change properties of multiple items at once
    :param request: must specify grid-type, value to be set, the field and ids of the objects to be modified
    :return:
    """
    grid_type = request.POST['grid-type']
    value = request.POST['value']
    field = request.POST['field']

    table = tables[grid_type]
    columns = table['columns']
    klass = table['class']
    ids = json.loads(request.POST.get('ids', '[]'))
    objs = klass.objects.filter(pk__in=ids)

    for column in columns:
        attr = column['slug']
        if attr == field:
            setter = column['setter']
            setter(objs, value, {'user': request.user})

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
                setter([obj], val, {'user': request.user})

    return HttpResponse('ok')


def set_action_values(request):
    """
    Change the value of ColumnActionValue whenever the user changes the orders/widths of the columns
    :param request:
    :return:
    """
    column_ids_actions_values = json.loads(request.POST.get('column-ids-action-values', None))
    grid_type = request.POST['grid-type']
    user = request.user

    for column in column_ids_actions_values.keys():
        actions_values = column_ids_actions_values[column]

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


def reorder_columns_handler(action_name, table_name, user, modified_columns):
    """
    Change the order of the column according to the index stored in ColumnActionValue
    :param action_name: name of the action as stored in ColumnActionValue
    :param table_name: name of the grid
    :param user: the logged in user
    :param modified_columns: a dict mapping name->column definition. It is originated from the column in tables.json
                             and might have been modified earlier by other values_grid_action_handlers function
    :return: modified_columns, after reordered
    """
    columns = tables[table_name]['columns']
    column_names = [x['slug'] for x in columns]
    column_values = ColumnActionValue.objects \
        .filter(user=user, action=action_name, table=table_name, column__in=column_names) \
        .values_list('column', 'value')

    action = actions[action_name]
    str2val = action['str2val']
    column_values = {k: str2val(v) for k,v in column_values}

    column_names = modified_columns.keys()
    column_names = sorted(column_names, key=lambda pk: str2val(column_values.get(pk, '-999999')))

    modified_columns = OrderedDict((k, modified_columns[k]) for k in column_names)

    return modified_columns


def set_column_width_handler(action_name, table_name, user, modified_columns):
    """
    Change widths of the columns according to the values stored in ColumnActionValue
    :param action_name: name of the action as stored in ColumnActionValue
    :param table_name: name of the grid
    :param user: the logged in user
    :param modified_columns: a dict mapping name->column definition. It is originated from the column in tables.json
                             and might have been modified earlier by other values_grid_action_handlers function
    :return: modified_columns, after changing width
    """
    columns = tables[table_name]['columns']
    column_names = [x['slug'] for x in columns]
    column_values = ColumnActionValue.objects \
        .filter(user=user, action=action_name, table=table_name, column__in=column_names) \
        .values_list('column', 'value')

    action = actions[action_name]
    str2val = action['str2val']

    for column, value in column_values:
        modified_columns[column]['width'] = str2val(value)
    return modified_columns


values_grid_action_handlers = {
    'reorder-columns': reorder_columns_handler,
    'set-column-width': set_column_width_handler
}

@csrf_exempt
def fetch_data(request, *args, **kwargs):
    """
    All fetch requests end up here and then delegated to the appropriate function, based on the POST key `type`
    :param request: must specify a valid `type` in POST data, otherwise 404. The type must be in form of
                    get_xxx_yyy and a function named set-xxx-yyy(request) must be available and registered
                    using register_app_modules
    :return: AJAX content
    """
    fetch_type = kwargs['type']
    module = kwargs.get('module', None)
    func_name = fetch_type.replace('-', '_')
    if isinstance(fetch_type, str):
        if module is not None:
            func_name = module + '.' + func_name
        function = globals().get(func_name, None)
        if function:
            retval = function(request)
            if retval:
                return retval
    retval = render(request, "errors/404.html")
    return HttpResponseNotFound(retval)


@csrf_exempt
def send_data(request, *args, **kwargs):
    """
    All get requests end up here and then delegated to the appropriate function, based on the POST key `type`
    :param request: must specify a valid `type` in POST data, otherwise 404. The type must be in form of
                    set_xxx_yyy and a function named set-xxx-yyy(request) must be available and registered
                    using register_app_modules
    :return: AJAX content
    """
    data_type = kwargs['type']
    func_name = data_type.replace('-', '_')
    if isinstance(data_type, str):
        function = globals().get(func_name, None)
        if function:
            retval = function(request)
            if retval:
                return retval
    retval = render(request, "errors/404.html")
    return HttpResponseNotFound(retval)


def get_view(name):
    """
    Get a generic TemplateBased view that uses only common context
    :param name: name of the view. A `name`.html must exist in the template folder
    :return:
    """
    class View(TemplateView):
        template_name = name + '.html'

        def get_context_data(self, **kwargs):
            context = super(View, self).get_context_data(**kwargs)
            context['page'] = name
            return context

    return View.as_view()


def register_app_modules(package, filename):
    """
    Make views and modules known to this workspace
    :param package: name of the package (app)
    :param filename: e.g. koe.views, koe.models, ...
    :return: None
    """
    package_modules = importlib.import_module('{}.{}'.format(package, filename)).__dict__
    globals_dict = globals()

    # First import all the modules made available in __all__
    exposed_modules = package_modules.get('__all__', [])
    for old_name in exposed_modules:
        new_name = '{}.{}'.format(package, old_name)
        globals_dict[new_name] = package_modules[old_name]

    # Then import all Models
    for old_name, module in package_modules.items():
        if not old_name in exposed_modules and isinstance(module, ModelBase):
            new_name = '{}.{}'.format(package, old_name)
            globals_dict[new_name] = module
