import json
from os.path import splitext

from django import template
from django.conf import settings
from django.urls import NoReverseMatch
from django.urls import reverse

from cms.models import HomePage
from root.models import MagicChoices

register = template.Library()


@register.filter
def shorten_name(name_ext):
    name, extension = splitext(name_ext)
    if name.__len__() > settings.MAX_FILE_NAME_LENGTH + 3:
        return "%s...%s" % (name[0:settings.MAX_FILE_NAME_LENGTH / 2], name[-settings.MAX_FILE_NAME_LENGTH / 2:])
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

        return u""


@register.tag(name='set')
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

    url_names = ['send-request', 'send-request']
    urls = {}
    for name in url_names:
        try:
            url = reverse(name)
        except NoReverseMatch:
            url = reverse(name, kwargs={'type': 'arg'})
        urls[name] = url

    return json.dumps({'literals': literals, 'aliases': aliases, 'urls': urls})


@register.simple_tag
def get_navbar_urls():
    return {
        'index': 'Syllable',
        'version': 'History',
    }


@register.simple_tag
def get_page_subpage_urls():
    return {
        'exemplars': ('Exemplars', [('label', 'By label'),
                                    ('label_family', 'By family'),
                                    ('label_subfamily', 'By subfamily')]),
        'songs': ('Songs', [('label', 'Using labels'),
                                ('label_family', 'Using family'),
                                ('label_subfamily', 'Using subfamily')])
    }


@register.simple_tag
def get_pages():
    """
    Return all the child pages of the first home page (The welcome page)
    :return: a list of HomePage instances that are children of the first HomePage
    """
    home_page_root = HomePage.objects.first()
    home_page_children = home_page_root.get_children().filter(live__exact=True)
    return home_page_children


@register.filter
def get_default_url(page):
    """
    Return the url according to the default site.
    The method url() provided by Page class doesn't work correctly when called without argument from the template
    :param page:
    :return:
    """
    return page.relative_url(page.get_site())
