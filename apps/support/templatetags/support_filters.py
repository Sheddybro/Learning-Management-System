from django import template

register = template.Library()

@register.filter
def filter_by_category(queryset, category):
    """
    Filters a queryset of FAQs by category.
    If category is None, it returns FAQs with no category.
    """
    if category is None:
        return queryset.filter(category__isnull=True)
    return queryset.filter(category=category)

@register.filter
def get_item(dictionary, key):
    """
    Gets an item from a dictionary by key.
    """
    return dictionary.get(key, 0)
