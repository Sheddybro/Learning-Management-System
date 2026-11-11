from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Custom template filter to get an item from a dictionary by key.
    Returns None if key doesn't exist or if not a dictionary.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def grade_letter(percentage):
    """Convert percentage to letter grade."""
    if percentage >= 90:
        return 'A+'
    elif percentage >= 85:
        return 'A'
    elif percentage >= 80:
        return 'A-'
    elif percentage >= 75:
        return 'B+'
    elif percentage >= 70:
        return 'B'
    elif percentage >= 65:
        return 'B-'
    elif percentage >= 60:
        return 'C+'
    elif percentage >= 55:
        return 'C'
    elif percentage >= 50:
        return 'C-'
    elif percentage >= 45:
        return 'D+'
    elif percentage >= 40:
        return 'D'
    elif percentage >= 33:
        return 'D-'
    else:
        return 'F'

@register.filter
def grade_class(percentage):
    """Convert percentage to CSS class for grade display."""
    if percentage >= 90:
        return 'a-plus'
    elif percentage >= 85:
        return 'a'
    elif percentage >= 80:
        return 'a-minus'
    elif percentage >= 75:
        return 'b-plus'
    elif percentage >= 70:
        return 'b'
    elif percentage >= 65:
        return 'b-minus'
    elif percentage >= 60:
        return 'c-plus'
    elif percentage >= 55:
        return 'c'
    elif percentage >= 50:
        return 'c-minus'
    elif percentage >= 45:
        return 'd-plus'
    elif percentage >= 40:
        return 'd'
    elif percentage >= 33:
        return 'd-minus'
    else:
        return 'f'
