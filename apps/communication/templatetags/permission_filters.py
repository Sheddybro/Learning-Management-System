from django import template
from django.contrib.auth.models import AnonymousUser

register = template.Library()


@register.filter
def has_perm(user, perm):
    """
    Template filter to check if a user has a specific permission.
    Usage: {% if user|has_perm:'app.codename' %}
    """
    if isinstance(user, AnonymousUser):
        return False
    return user.has_perm(perm)
