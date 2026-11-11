import logging

logger = logging.getLogger(__name__)


def site(request):
    """
    Adds `site` and `site_name` to template contexts. Uses django.contrib.sites if available.
    """
    try:
        from django.contrib.sites.models import Site

        current = Site.objects.get_current()
        site_name = getattr(current, "name", "")
        return {"site": current, "site_name": site_name}
    except Exception:
        logger.debug("django.contrib.sites not available or unable to get current site")
        return {"site": None, "site_name": ""}
