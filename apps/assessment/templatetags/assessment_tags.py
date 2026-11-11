from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def to_option_letter(value):
    """
    Convert a number to an option letter (1 -> A, 2 -> B, etc.)
    """
    if not isinstance(value, int) or value < 1:
        return str(value)

    # ASCII 'A' is 65, so we subtract 1 and add 65
    return chr(64 + value)

@register.filter
def get_range(value):
    """
    Return a range object from 1 to value (inclusive)
    """
    try:
        return range(1, int(value) + 1)
    except (ValueError, TypeError):
        return range(1, 1)

@register.filter
@stringfilter
def split(value, arg):
    """
    Split a string by a separator
    """
    return value.split(arg)

@register.simple_tag
def get_item(dictionary, key):
    """
    Get an item from a dictionary
    """
    return dictionary.get(key)
