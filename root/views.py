import datetime
import importlib
import json
from collections import OrderedDict

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import ForeignKey, ManyToManyField
from django.db.models.base import ModelBase
from django.db.models.fields.reverse_related import ForeignObjectRel
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseServerError,
    StreamingHttpResponse,
)
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from dotmap import DotMap
from tz_detect.utils import offset_to_timezone

from koe import jsons
from root.exceptions import CustomAssertionError
from root.models import (
    ColumnActionValue,
    ExtraAttr,
    ExtraAttrValue,
    ValueTypes,
    get_bulk_id,
    get_field,
    has_field,
    value_getter,
    value_setter,
)


error_tracker = settings.ERROR_TRACKER

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
    if "getter" in table:
        getter = table["getter"]
        ids, rows = getter(objs, extras)
    else:
        ids = get_bulk_id(objs)
        attrs = {}
        rows = []
        for column in table["columns"]:
            if column["is_addon"]:
                continue
            getter = column["getter"]
            attr = column["slug"]
            value = getter(objs, extras)
            attrs[attr] = value

        for id in ids:
            row = {"id": id}
            for attr in attrs:
                row[attr] = attrs[attr][id]
            rows.append(row)

    table_editable = table["table-editable"]
    if callable(table_editable):
        table_editable = table_editable(extras)

    get_row_editability = table["row-editable"]

    if not table_editable:
        return rows

    viewas = extras.viewas
    if not viewas or viewas == extras.user.username:
        if get_row_editability is not None:
            editabilities = get_row_editability(objs, extras)

            for row in rows:
                id = row["id"]
                row_editable = editabilities[id]
                if row_editable != table_editable:
                    row["__editable"] = row_editable

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
        klass = global_namespace[table["class"]]
        table["class"] = klass

        has_bulk_getter = "getter" in table

        if has_bulk_getter:
            table["getter"] = global_namespace[table["getter"]]

        table["table-editable"] = getattr(klass, "get_table_editability", True)
        table["row-editable"] = getattr(klass, "get_row_editability", None)
        table["filter"] = getattr(klass, "filter", None)

        for column in table["columns"]:
            has_setter = "setter" in column
            is_addon = column.get("is_addon", False)
            column["is_addon"] = is_addon

            slug = column["slug"]
            _type = column["type"]
            _type = ValueTypes.get_key_val_pairs()[_type]
            column["type"] = _type
            column["editor"] = column.get("editor", ValueTypes.get_associated_value(_type, "editor"))
            column["formatter"] = column.get("formatter", ValueTypes.get_associated_value(_type, "formatter"))
            column["filter"] = ValueTypes.get_associated_value(_type, "filter_type")
            column["sortable"] = ValueTypes.get_associated_value(_type, "sortable")
            column["copyable"] = ValueTypes.get_associated_value(_type, "copyable")
            column["exportable"] = column.get("exportable", ValueTypes.get_associated_value(_type, "exportable"))
            column["cssClass"] = column.get("css_class", "")

            if "has_total" not in column:
                column["has_total"] = False

            is_attribute = column.get("is_attribute", False)
            is_extra_attr = column.get("is_extra_attr", False)

            editable = column.get("editable", False)
            if editable not in [True, False]:
                editable = getattr(klass, "get_{}".format(editable))
            column["editable"] = editable

            importable = editable and column.get("importable", ValueTypes.get_associated_value(_type, "importable"))
            column["importable"] = importable

            if not has_bulk_getter:
                getter = getattr(klass, "get_{}".format(slug), None)
                if getter is None:
                    if is_attribute:
                        getter = klass.get_FIELD(slug)
                    elif is_extra_attr:
                        getter = klass.get_EXTRA_FIELD(slug)
                column["getter"] = getter

            if has_setter:
                setter = getattr(klass, column["setter"], None)
                if setter is None:
                    setter = global_namespace[column["setter"]]
            else:
                setter = getattr(klass, "set_{}".format(slug), None)
                if setter is None:
                    if is_attribute:
                        setter = klass.set_FIELD(slug)
                    elif is_extra_attr:
                        setter = klass.set_EXTRA_FIELD(slug)
            if editable:
                column["setter"] = setter

            if is_extra_attr:
                ExtraAttr.objects.get_or_create(klass=klass.__name__, type=_type, name=slug)

            if "total_label" not in column:
                column["total_label"] = "-/-"

            if column["formatter"] == "Select":
                choice_class = global_namespace[column["choices"]]
                choises = choice_class.as_choices()
                column["options"] = {x: y for x, y in choises}

    actions = jsons.actions
    for slug in actions:
        action = actions[slug]
        _type = action["type"]
        _type = ValueTypes.get_key_val_pairs()[_type]

        action["type"] = _type
        action["val2str"] = value_setter[_type]
        action["str2val"] = value_getter[_type]


def get_grid_column_definition(request):
    """
    Return slickgrid's array of column definitions
    :param request: must specify grid-type
    :return:
    """
    user = request.user
    table_name = request.POST["grid-type"]
    table = tables[table_name]
    extras = json.loads(request.POST.get("extras", "{}"))
    extras["user"] = user

    table_editable = table["table-editable"]
    if callable(table_editable):
        table_editable = table_editable(extras)

    viewas = extras.get("viewas", user.username)
    user_is_editing = viewas == user.username

    columns = []

    for column in table["columns"]:
        slug = column["slug"]
        is_addon = column["is_addon"]

        editable = column["editable"] and user_is_editing
        total_label = column["total_label"]
        editor = column["editor"]
        formatter = column["formatter"]
        has_total = column["has_total"]
        sortable = column["sortable"]
        filter = column["filter"]
        css_class = column["cssClass"]
        copyable = column["copyable"]
        exportable = column["exportable"]
        importable = column["importable"]

        if callable(editable):
            editable = table_editable
        else:
            editable = editable and table_editable

        col_def = dict(
            id=slug,
            field=slug,
            editable=editable,
            editor=editor,
            filter=filter,
            formatter=formatter,
            sortable=sortable,
            hasTotal=has_total,
            totalLabel=total_label,
            cssClass=css_class,
            copyable=copyable,
            exportable=exportable,
            importable=importable,
        )

        if "options" in column:
            col_def["options"] = column["options"]

        if not is_addon:
            col_def["name"] = column["name"]

        if editable:
            col_def["cssClass"] += " editable"

        columns.append(col_def)

    col_id_to_col = {x["id"]: x for x in columns}
    action_names = list(actions.keys())

    for action_name in action_names:
        handler = values_grid_action_handlers[action_name]
        col_id_to_col = handler(action_name, table_name, user, col_id_to_col)

    columns = list(col_id_to_col.values())

    # Final column is for the actions
    columns.append(
        {
            "id": "actions",
            "field": "actions",
            "name": "Actions",
            "actions": action_names,
            "formatter": "Action",
        }
    )

    return dict(origin="get_grid_column_definition", success=True, warning=None, payload=columns)


def get_grid_content(request):
    """
    Get the configuration of the specified table from tables.json
    Then return the data according to the table's getters
    :param request:
    :return:
    """
    today = datetime.date.today()
    now = timezone.now()
    tz_offset = request.session["detected_tz"]
    tz = offset_to_timezone(tz_offset)

    extras = DotMap(today=today, now=now, user=request.user, tz=tz)
    grid_type = request.POST["grid-type"]
    extra_args = json.loads(request.POST.get("extras", {}))
    for key, value in extra_args.items():
        extras[key] = value

    table = tables[grid_type]
    klass = table["class"]
    filter = table["filter"]
    if filter is None:
        objs = klass.objects.all()
    else:
        objs = filter(extras)
    rows = get_attrs(objs, table, extras)
    return dict(origin="get_grid_content", success=True, warning=None, payload=rows)


def set_property_bulk(request):
    """
    Change properties of multiple items at once
    :param request: must specify grid-type, value to be set, the field and ids of the objects to be modified
    :return:
    """
    grid_type = request.POST["grid-type"]
    value = request.POST["value"]
    field = request.POST["field"]

    table = tables[grid_type]
    columns = table["columns"]
    klass = table["class"]
    ids = json.loads(request.POST.get("ids", "[]"))
    objs = klass.objects.filter(pk__in=ids)

    if has_field(klass, "user"):
        user_ids = list(klass.objects.values_list("user__id", flat=True).distinct())
        if len(user_ids) == 0 or len(user_ids) > 1 or user_ids[0] != request.user.id:
            raise CustomAssertionError("You don' have permission to change data that doesn't belong to you")

    for column in columns:
        attr = column["slug"]
        if attr == field:
            setter = column["setter"]
            setter(objs, value, DotMap(user=request.user))

    return dict(origin="set_property_bulk", success=True, warning=None, payload=True)


def change_properties(request):
    """
    When the user changes a row on the table, we will save the new value to the database, then return the updated row
    together with the total row, so that the view can update the table.
    :param request:
    :return:
    """
    grid_row = json.loads(request.POST["property"])
    grid_type = request.POST["grid-type"]

    table = tables[grid_type]
    columns = table["columns"]
    klass = table["class"]
    obj = klass.objects.get(pk=grid_row["id"])

    if issubclass(klass, ExtraAttrValue) and has_field(klass, "user"):
        if obj.user != request.user:
            raise CustomAssertionError("You don' have permission to change data that doesn't belong to you")

    for column in columns:
        attr = column["slug"]
        editable = column["editable"]
        if editable and attr in grid_row:
            val = grid_row[attr]
            if "setter" in column:
                setter = column["setter"]
                setter([obj], val, DotMap(user=request.user))

    return dict(origin="change_properties", success=True, warning=None, payload=True)


def _change_properties_table(rows, grid_type, missing_attrs, attrs, user):
    # The last attribute in a row is always the ID
    ids = [x[-1] for x in rows]

    table = tables[grid_type]
    columns = table["columns"]
    klass = table["class"]
    objs = klass.objects.filter(id__in=ids)

    attr_editability = {c["slug"]: c["editable"] for c in columns}
    attr_setter = {c["slug"]: c.get("setter", None) for c in columns}
    id2obj = {x.id: x for x in objs}

    bulk_list = {
        x: ([], [])
        for x in attrs
        if x not in missing_attrs and attr_editability.get(x, False) and attr_setter.get(x, None)
    }

    bulk_setter = {
        x: attr_setter.get(x, None)
        for x in attrs
        if x not in missing_attrs and attr_editability.get(x, False) and attr_setter.get(x, None)
    }

    for row_idx, row in enumerate(rows):
        for attr_idx, attr in enumerate(attrs):
            if attr in bulk_list:
                row_id = ids[row_idx]
                obj = id2obj[row_id]
                value = row[attr_idx]

                (bulk, vals) = bulk_list[attr]

                bulk.append(obj)
                vals.append(value)

    with transaction.atomic():
        for attr, (bulk, vals) in bulk_list.items():
            setter = bulk_setter[attr]

            # if the field is native and not foreign key to this model,
            # we can bulk set multiple objects with multiple values
            field = get_field(klass, attr)
            if field and not isinstance(field, (ManyToManyField, ForeignObjectRel, ForeignKey)):
                setter(bulk, vals, DotMap(user=user))

            # Otherwise there is no way but to bulk set multiple objects that share the same value
            else:
                val2bulk = {}
                for val, obj in zip(vals, bulk):
                    if val not in val2bulk:
                        val2bulk[val] = [obj]
                    else:
                        val2bulk[val].append(obj)
                for val, bulk in val2bulk.items():
                    setter(bulk, val, DotMap(user=user))


def change_properties_table(request):
    """
    Similar to change_properties, but this takes input from an array of rows
    :param request:
    :return:
    """
    rows = json.loads(request.POST["rows"])
    grid_type = request.POST["grid-type"]
    missing_attrs = json.loads(request.POST["missing-attrs"])
    attrs = json.loads(request.POST["attrs"])
    user = request.user

    retval = _change_properties_table(rows, grid_type, missing_attrs, attrs, user)
    return dict(origin="change_properties_table", success=True, warning=None, payload=retval)


def change_extra_attr_value(request):
    """
    Call to change one extra_attr_value
    :param request: must contain the field 'value', 'klass', 'owner' and 'attr' in POST
    :return:
    """
    attr = request.POST["attr"]
    klass = request.POST["klass"]
    owner_id = int(request.POST.get("owner", request.user.id))
    value = request.POST["value"]

    extra_attr_value = ExtraAttrValue.objects.filter(user=request.user, owner_id=owner_id, attr__name=attr).first()
    if extra_attr_value is None:
        extra_attr_value = ExtraAttrValue()
        extra_attr_value.user = request.user
        extra_attr_value.owner_id = owner_id
        extra_attr_value.attr = ExtraAttr.objects.get(klass=klass, name=attr)
    extra_attr_value.value = value
    extra_attr_value.save()

    return dict(origin="change_extra_attr_value", success=True, warning=None, payload=True)


def set_action_values(request):
    """
    Change the value of ColumnActionValue whenever the user changes the orders/widths of the columns
    :param request:
    :return:
    """
    column_ids_actions_values = json.loads(request.POST.get("column-ids-action-values", None))
    grid_type = request.POST["grid-type"]
    user = request.user

    for column in column_ids_actions_values.keys():
        actions_values = column_ids_actions_values[column]

        for action in actions_values:
            value = actions_values[action]
            action_definition = actions[action]
            val2str = action_definition["val2str"]
            value = val2str(value)

            assert value is not None, "actions_values = {}".format(json.dumps(actions_values))

            action_values = ColumnActionValue.objects.filter(user=user, action=action, column=column, table=grid_type)
            action_value = action_values.first()
            if len(action_values) > 1:
                for av in action_values[1:]:
                    av.delete()

            if action_value is None:
                action_value = ColumnActionValue()
                action_value.action = action
                action_value.column = column
                action_value.table = grid_type
                action_value.user = user
            action_value.value = val2str(value)
            action_value.save()
    return dict(origin="set_action_values", success=True, warning=None, payload=True)


def _reorder_columns_handler(action_name, table_name, user, modified_columns):
    """
    Change the order of the column according to the index stored in ColumnActionValue
    :param action_name: name of the action as stored in ColumnActionValue
    :param table_name: name of the grid
    :param user: the logged in user
    :param modified_columns: a dict mapping name->column definition. It is originated from the column in tables.json
                             and might have been modified earlier by other values_grid_action_handlers function
    :return: modified_columns, after reordered
    """
    columns = tables[table_name]["columns"]
    column_names = [x["slug"] for x in columns]
    column_values = ColumnActionValue.objects.filter(
        user=user, action=action_name, table=table_name, column__in=column_names
    ).values_list("column", "value")

    action = actions[action_name]
    str2val = action["str2val"]
    column_values = {k: str2val(v) for k, v in column_values}

    column_names = modified_columns.keys()
    column_names = sorted(column_names, key=lambda pk: str2val(column_values.get(pk, "-999999")))

    modified_columns = OrderedDict((k, modified_columns[k]) for k in column_names)

    return modified_columns


def _set_column_width_handler(action_name, table_name, user, modified_columns):
    """
    Change widths of the columns according to the values stored in ColumnActionValue
    :param action_name: name of the action as stored in ColumnActionValue
    :param table_name: name of the grid
    :param user: the logged in user
    :param modified_columns: a dict mapping name->column definition. It is originated from the column in tables.json
                             and might have been modified earlier by other values_grid_action_handlers function
    :return: modified_columns, after changing width
    """
    columns = tables[table_name]["columns"]
    column_names = [x["slug"] for x in columns]
    column_values = ColumnActionValue.objects.filter(
        user=user, action=action_name, table=table_name, column__in=column_names
    ).values_list("column", "value")

    action = actions[action_name]
    str2val = action["str2val"]

    for column, value in column_values:
        modified_columns[column]["width"] = str2val(value)
    return modified_columns


values_grid_action_handlers = {
    "reorder-columns": _reorder_columns_handler,
    "set-column-width": _set_column_width_handler,
}


def exception_handler(function, request, *args, **kwargs):
    try:
        return function(request, *args, **kwargs)
    except Exception as e:
        error_id = error_tracker.captureException()
        if isinstance(e, IntegrityError):
            message = e.args[1]
        else:
            message = str(e)

        if isinstance(e, CustomAssertionError):
            return HttpResponseBadRequest(json.dumps(dict(errid=error_id, payload=message)))
        return HttpResponseServerError(json.dumps(dict(errid=error_id, payload=message)))


def can_have_exception(function):
    def wrap(request, *args, **kwargs):
        return exception_handler(function, request, *args, **kwargs)

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


@csrf_exempt
def send_request(request, *args, **kwargs):
    """
    All fetch requests end up here and then delegated to the appropriate function, based on the POST key `type`
    :param request: must specify a valid `type` in POST data, otherwise 404. The type must be in form of
                    get_xxx_yyy and a function named set-xxx-yyy(request) must be available and registered
                    using register_app_modules
    :return: AJAX content
    """
    fetch_type = kwargs["type"]
    module = kwargs.get("module", None)
    func_name = fetch_type.replace("-", "_")
    if isinstance(fetch_type, str):
        if module is not None:
            func_name = module + "." + func_name
        function = globals().get(func_name, None)

        if function:
            response = exception_handler(function, request)
            if isinstance(response, (HttpResponse, StreamingHttpResponse)):
                return response
            if isinstance(response, dict):
                return HttpResponse(json.dumps(response))
            return HttpResponse(json.dumps(dict(success=True, warning=None, payload=response)))

    return HttpResponseNotFound()


def get_view(name):
    """
    Get a generic TemplateBased view that uses only common context
    :param name: name of the view. A `name`.html must exist in the template folder
    :return:
    """

    class View(TemplateView):
        template_name = name + ".html"

        def get_context_data(self, **kwargs):
            context = super(View, self).get_context_data(**kwargs)
            context["page"] = name
            return context

    return View.as_view()


def register_app_modules(package, filename):
    """
    Make views and modules known to this workspace
    :param package: name of the package (app)
    :param filename: e.g. koe.views, koe.models, ...
    :return: None
    """
    package_modules = importlib.import_module("{}.{}".format(package, filename)).__dict__
    globals_dict = globals()

    # First import all the modules made available in __all__
    exposed_modules = package_modules.get("__all__", [])
    for old_name in exposed_modules:
        new_name = "{}.{}".format(package, old_name)
        globals_dict[new_name] = package_modules[old_name]

    # Then import all Models
    for old_name, module in package_modules.items():
        if old_name not in exposed_modules and isinstance(module, ModelBase):
            new_name = "{}.{}".format(package, old_name)
            globals_dict[new_name] = module
