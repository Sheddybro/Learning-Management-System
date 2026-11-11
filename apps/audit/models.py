from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import CoreBaseModel


class AuditLog(CoreBaseModel):
    """
    Model for tracking system-wide audit events.
    """

    class ActionType(models.TextChoices):
        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")
        DELETE = "delete", _("Delete")
        LOGIN = "login", _("Login")
        LOGOUT = "logout", _("Logout")
        VIEW = "view", _("View")
        EXPORT = "export", _("Export")
        IMPORT = "import", _("Import")

    institution = models.ForeignKey(
        "core.Institution",
        on_delete=models.CASCADE,
        related_name="audit_logs",
        verbose_name=_("institution"),
        help_text=_("Institution this audit log belongs to"),
        null=True,
        blank=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("user"),
    )
    action = models.CharField(_("action"), max_length=20, choices=ActionType.choices)
    model_name = models.CharField(_("model name"), max_length=100)
    object_id = models.CharField(_("object id"), max_length=100)
    details = models.JSONField(_("details"), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.TextField(_("user agent"), blank=True, null=True)
    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"
