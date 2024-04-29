import json
import os
from os.path import splitext

from django import template
from django.conf import settings
from django.urls import NoReverseMatch, reverse

from root.models import MagicChoices


register = template.Library()


@register.filter
def shorten_name(name_ext):
    name, extension = splitext(name_ext)
    if name.__len__() > settings.MAX_FILE_NAME_LENGTH + 3:
        return "%s...%s" % (
            name[0 : settings.MAX_FILE_NAME_LENGTH / 2],
            name[-settings.MAX_FILE_NAME_LENGTH / 2 :],
        )
    else:
        return name


class SetVarNode(template.Node):
    def __init__(self, var_name, var_value):
        self.var_name = var_name
        self.var_value = var_value

    def render(self, context):
        try:
            value = template.Variable(self.var_value).resolve(context)
        except template.VariableDoesNotExist:
            value = ""
        context[self.var_name] = value

        return ""


@register.tag(name="set")
def set_var(parser, token):
    """
    {% set some_var = '123' %}
    """
    parts = token.split_contents()
    if len(parts) < 4:
        raise template.TemplateSyntaxError("'set' tag must be of the form: {% set <var_name> = <var_value> %}")

    return SetVarNode(parts[1], parts[3])


@register.simple_tag
def get_server_constants():
    classes = MagicChoices.__subclasses__()
    literals = {}
    aliases = {}
    for cl in classes:
        choices = cl.get_key_val_pairs()
        literals[cl.__name__] = choices

        cl_aliases = cl.get_aliases()
        if cl_aliases:
            alias_dict = {}
            for key in cl_aliases:
                alias_dict[key] = cl_aliases[key]
            aliases[cl.__name__] = alias_dict

    url_names = ["send-request", "send-request"]
    urls = {}
    for name in url_names:
        try:
            url = reverse(name)
        except NoReverseMatch:
            url = reverse(name, kwargs={"type": "arg"})
        urls[name] = url

    return json.dumps({"literals": literals, "aliases": aliases, "urls": urls, "consts": settings.CONSTS})


@register.simple_tag
def get_navbar_urls():
    pages = [
        dict(
            text="Syllables",
            is_single=False,
            url=reverse("syllables"),
            subpages=[
                dict(text="Label syllables", is_single=True, url=reverse("syllables")),
                dict(text="Restore version", is_single=True, url=reverse("version")),
            ],
        ),
        dict(
            text="Exemplars",
            is_single=False,
            url=reverse("exemplars"),
            subpages=[
                dict(
                    text="By label",
                    is_single=True,
                    url=reverse("exemplars", args=["label"]),
                ),
                dict(
                    text="By family",
                    is_single=True,
                    url=reverse("exemplars", args=["label_family"]),
                ),
                dict(
                    text="By subfamily",
                    is_single=True,
                    url=reverse("exemplars", args=["label_subfamily"]),
                ),
            ],
        ),
        dict(
            text="Songs",
            is_single=False,
            url=reverse("songs"),
            subpages=[
                dict(
                    text="Using label",
                    is_single=True,
                    url=reverse("songs", args=["label"]),
                ),
                dict(
                    text="Using family",
                    is_single=True,
                    url=reverse("songs", args=["label_family"]),
                ),
                dict(
                    text="Using subfamily",
                    is_single=True,
                    url=reverse("songs", args=["label_subfamily"]),
                ),
            ],
        ),
        dict(
            text="Analysis",
            is_single=False,
            url=reverse("sequence-mining"),
            subpages=[
                dict(
                    text="Feature extraction & clustering",
                    is_single=True,
                    url=reverse("feature-extraction"),
                ),
                dict(
                    text="Sequence mining by label",
                    is_single=True,
                    url=reverse("sequence-mining", args=["label"]),
                ),
                dict(
                    text="Sequence mining by family",
                    is_single=True,
                    url=reverse("sequence-mining", args=["label_family"]),
                ),
                dict(
                    text="Sequence mining by subfamily",
                    is_single=True,
                    url=reverse("sequence-mining", args=["label_subfamily"]),
                ),
            ],
        ),
    ]

    return pages


@register.simple_tag
def get_granularity():
    return ["label", "label_subfamily", "label_family"]


@register.simple_tag
def get_auto_segment():
    return ["Harma"]


# @register.filter
# def get_default_url(page):
#     """
#     Return the url according to the default site.
#     The method url() provided by Page class doesn't work correctly when called without argument from the template
#     :param page:
#     :return:
#     """
#     try:
#         site = page.get_site()
#     except Exception:
#         site = None
#     return page.relative_url(site)


@register.simple_tag
def debug_mode():
    """
    Whether or not the website is running in debug mode
    :return:
    """
    return settings.DEBUG
