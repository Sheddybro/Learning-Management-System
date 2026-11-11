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


@register.filter
def replace_underscores(value):
    return str(value or "").replace("_", "-")


@register.filter
def contains(value, text):
    return str(text) in str(value or "")


@register.filter
def add_months(value, months):
    """Advance a date by whole calendar months while clamping month-end days."""
    import calendar
    from datetime import date, datetime

    if not isinstance(value, (date, datetime)):
        return value
    try:
        offset = int(months)
    except (ValueError, TypeError):
        return value
    month_index = value.year * 12 + value.month - 1 + offset
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


@register.filter
def average_gpa(results):
    """Average the stored grade points on graded assessment results."""
    values = [result.grade.grade_point for result in (results or [])
              if getattr(result, 'grade', None) is not None]
    return sum(values) / len(values) if values else 0


@register.filter
def highest_gpa(results):
    values = [result.grade.grade_point for result in (results or [])
              if getattr(result, 'grade', None) is not None]
    return max(values) if values else 0


@register.filter
def add_years(value, years):
    """Advance a date safely, including February 29 on non-leap years."""
    from datetime import date, datetime

    if not isinstance(value, (date, datetime)):
        return value
    try:
        return value.replace(year=value.year + int(years))
    except ValueError:
        return value.replace(year=value.year + int(years), month=2, day=28)
    except TypeError:
        return value


@register.filter
def pass_rate(results):
    graded = [result for result in (results or [])
              if getattr(result, 'grade', None) is not None]
    if not graded:
        return 0
    passing = sum(1 for result in graded if result.grade.grade_point > 0)
    return round(100 * passing / len(graded), 1)
