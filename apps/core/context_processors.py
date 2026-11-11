import logging
from .middleware import get_current_institution, get_user_accessible_institutions
from .models import Institution

logger = logging.getLogger(__name__)


def tenant_context(request):
    """
    Context processor for tenant/multi-tenancy information (legacy function).
    """
    current_inst = get_current_institution()
    user_institutions = []

    if request.user.is_authenticated:
        user_institutions = get_user_accessible_institutions(request.user)

    return {
        "tenant_institution": current_inst,
        "user_institutions": user_institutions,
        "multi_tenant_enabled": True,
    }


def current_institution(request):
    """
    Context processor to add current institution information to all template contexts.
    """
    try:
        institution = get_current_institution()

        if institution:
            return {
                "current_institution": institution,
                "institution_code": institution.code,
                "institution_name": institution.name,
                "institution_theme": getattr(institution, "theme", None),
            }
        else:
            return {
                "current_institution": None,
                "institution_code": None,
                "institution_name": None,
                "institution_theme": None,
            }
    except Exception as e:
        logger.warning(f"Error in current_institution context processor: {e}")
        return {
            "current_institution": None,
            "institution_code": None,
            "institution_name": None,
            "institution_theme": None,
        }


def sidebar_menu_context(request):
    """
    Context processor to add sidebar menu expansion states to all template contexts.
    """
    try:
        app_name = request.resolver_match.app_name if request.resolver_match else ""
        url_name = request.resolver_match.url_name if request.resolver_match else ""

        # Administration menu expansion logic
        administration_expanded = (
            "users" in app_name
            or "audit" in app_name
            or ("analytics" in app_name and url_name == "settings")
            or (
                "core" in app_name
                and (
                    url_name == "super_admin_dashboard"
                    or url_name == "super_admin_entities"
                    or url_name == "institution_list"
                )
            )
        )

        return {
            "sidebar_administration_expanded": administration_expanded,
        }
    except Exception as e:
        logger.warning(f"Error in sidebar_menu_context context processor: {e}")
        return {
            "sidebar_administration_expanded": False,
        }


def ui_config_context(request):
    """
    Context processor to add UI configuration settings to all template contexts.
    Provides system-wide and institution-specific UI configurations.
    Also provides user theme preference.
    """
    try:
        from .models import SystemConfig, InstitutionConfig

        ui_config = {}
        institution = get_current_institution()

        # Get all active UI system configurations
        ui_system_configs = SystemConfig.objects.filter(
            config_type="ui", status="active"
        ).select_related()

        for config in ui_system_configs:
            # Check if institution has an override
            if institution:
                try:
                    institution_config = InstitutionConfig.objects.get(
                        institution=institution, system_config=config, is_active=True
                    )
                    ui_config[config.key] = institution_config.effective_value
                except InstitutionConfig.DoesNotExist:
                    ui_config[config.key] = config.value
            else:
                ui_config[config.key] = config.value

        # Get user theme preference
        user_theme = "light"  # Default theme
        if (
            request.user.is_authenticated
            and hasattr(request.user, "profile")
            and request.user.profile
        ):
            user_theme = request.user.profile.theme

        return {
            "ui_config": ui_config,
            "user_theme": user_theme,
        }
    except Exception as e:
        logger.warning(f"Error in ui_config_context context processor: {e}")
        return {
            "ui_config": {},
            "user_theme": "light",
        }
