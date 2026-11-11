from django import template

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
    except ValueError:
        return 0
