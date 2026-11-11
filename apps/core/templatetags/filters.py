from django import template
from pathlib import PurePath
import json

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Custom template filter to get an item from a dictionary using a key.
    Usage: {{ my_dict|get_item:my_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def div(value, arg):
    """
    Custom template filter to divide value by arg.
    Usage: {{ value|div:arg }}
    """
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0


@register.filter
def mul(value, arg):
    """
    Custom template filter to multiply value by arg.
    Usage: {{ value|mul:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def multiply(value, arg):
    return mul(value, arg)


@register.filter
def divide(value, arg):
    return div(value, arg)


@register.filter
def sub(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name="filename")
def file_basename(value):
    return PurePath(str(value or "")).name


@register.filter(name="map")
def project_list(values, key):
    """Serialize a list of model/dictionary attributes for chart JavaScript."""
    result = []
    for item in values or []:
        if isinstance(item, dict):
            result.append(item.get(key))
        else:
            result.append(getattr(item, key, None))
    return json.dumps(result, default=str)


@register.filter
def split_lines(value):
    return str(value or "").splitlines()


@register.filter
def config_field(form, config_id):
    name = f"config_{config_id}"
    return form[name] if name in form.fields else ""
