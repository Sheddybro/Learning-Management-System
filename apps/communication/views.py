# apps/communication/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q, Count, Max
from django.utils import timezone
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
import json

from .models import (
    Announcement,
    NoticeBoard,
    NoticeBoardItem,
    EmailTemplate,
    SentEmail,
    SMSTemplate,
    SentSMS,
    RealTimeNotification,
    NotificationPreference,
    NotificationTemplate,
    ChatRoom,
    ChatMessage,
    ChatParticipant,
    TypingIndicator,
    Message,
    MessageRecipient,
)
from .forms import MessageForm
from apps.users.models import User
from apps.academics.models import Class, Student


# Announcement Views
class CommunicationAccessMixin:
    """Mixin to check communication-related permissions"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Check if user has communication-related role or is staff/admin
        user_roles = request.user.user_roles.all()
        communication_roles = ["admin", "principal", "super_admin"]

        if not any(role.role.role_type in communication_roles for role in user_roles):
            if not request.user.is_staff:
                # Regular users can access basic communication features
                pass  # Allow access for basic features

        return super().dispatch(request, *args, **kwargs)


class CommunicationStaffRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is staff or admin for communication management."""

    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True

        # Check if user has admin role
        return (
            user.has_perm("communication.change_announcement")
            or user.user_roles.filter(
                role__role_type__in=[
                    "admin",
                    "principal",
                    "school_admin",
                    "super_admin",
                ]
            ).exists()
        )


class AnnouncementListView(LoginRequiredMixin, CommunicationAccessMixin, ListView):
    model = Announcement
    template_name = "communication/announcements/announcement_list.html"
    context_object_name = "announcements"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            Announcement.objects.filter(is_published=True, status="active")
            .select_related("author")
            .prefetch_related("specific_users")
        )

        # Filter by type if provided
        announcement_type = self.request.GET.get("type")
        if announcement_type:
            queryset = queryset.filter(announcement_type=announcement_type)

        # Filter by audience
        user = self.request.user
        if hasattr(user, "student_profile"):
            queryset = queryset.filter(
                Q(target_audience="all")
                | Q(target_audience="students")
                | Q(specific_users=user)
                | Q(
                    specific_classes__in=user.student_profile.enrollments.values_list(
                        "class_enrolled", flat=True
                    )
                )
            ).distinct()
        elif hasattr(user, "teacher_profile"):
            queryset = queryset.filter(
                Q(target_audience="all")
                | Q(target_audience="teachers")
                | Q(specific_users=user)
            ).distinct()
        elif (
            user.has_perm("academics.view_student")
            or user.user_roles.filter(role__role_type="parent").exists()
        ):
            # Parent can see announcements targeted to parents, all users, or specific to their children
            from apps.users.models import ParentStudentRelationship

            children_classes = (
                ParentStudentRelationship.objects.filter(parent=user, status="active")
                .values_list("student__enrollments__class_enrolled", flat=True)
                .distinct()
            )

            queryset = queryset.filter(
                Q(target_audience="all")
                | Q(target_audience="parents")
                | Q(specific_users=user)
                | Q(specific_classes__in=children_classes)
            ).distinct()

        return queryset.order_by("-is_pinned", "-published_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["announcement_types"] = Announcement.AnnouncementType.choices
        context["selected_type"] = self.request.GET.get("type", "")
        return context


class AnnouncementDetailView(LoginRequiredMixin, DetailView):
    model = Announcement
    template_name = "communication/announcements/announcement_detail.html"
    context_object_name = "announcement"

    def get_queryset(self):
        return Announcement.objects.select_related("author")


class AnnouncementCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Announcement
    template_name = "communication/announcements/announcement_form.html"
    fields = [
        "title",
        "content",
        "announcement_type",
        "priority",
        "target_audience",
        "specific_users",
        "specific_classes",
        "is_published",
        "schedule_publish",
        "expires_at",
        "is_pinned",
        "pin_until",
        "banner_image",
        "attachments",
    ]
    permission_required = "communication.add_announcement"

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, "Announcement created successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "communication:announcement_detail", kwargs={"pk": self.object.pk}
        )


class AnnouncementUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Announcement
    template_name = "communication/announcements/announcement_form.html"
    fields = [
        "title",
        "content",
        "announcement_type",
        "priority",
        "target_audience",
        "specific_users",
        "specific_classes",
        "is_published",
        "schedule_publish",
        "expires_at",
        "is_pinned",
        "pin_until",
        "banner_image",
        "attachments",
    ]
    permission_required = "communication.change_announcement"

    def form_valid(self, form):
        messages.success(self.request, "Announcement updated successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "communication:announcement_detail", kwargs={"pk": self.object.pk}
        )


class AnnouncementDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Announcement
    template_name = "communication/announcements/announcement_confirm_delete.html"
    context_object_name = "announcement"
    permission_required = "communication.delete_announcement"
    success_url = reverse_lazy("communication:announcement_list")

    def get_queryset(self):
        # Users can only delete their own announcements unless they have admin permission
        if self.request.user.has_perm("communication.admin_delete_announcement"):
            return Announcement.objects.all()
        else:
            return Announcement.objects.filter(author=self.request.user)

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Announcement "{self.object.title}" has been deleted successfully!',
        )
        return super().form_valid(form)


# Notice Board Views
class NoticeBoardListView(LoginRequiredMixin, ListView):
    model = NoticeBoard
    template_name = "communication/noticeboards/noticeboard_list.html"
    context_object_name = "notice_boards"

    def get_queryset(self):
        return NoticeBoard.objects.filter(
            is_active=True, status="active"
        ).prefetch_related("announcements", "allowed_users")


class NoticeBoardDisplayView(LoginRequiredMixin, DetailView):
    model = NoticeBoard
    template_name = "communication/noticeboards/noticeboard_display.html"
    context_object_name = "notice_board"

    def get_queryset(self):
        return NoticeBoard.objects.prefetch_related("noticeboarditem_set__announcement")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get active announcements for this board
        active_items = (
            self.object.noticeboarditem_set.filter(is_active=True, status="active")
            .select_related("announcement")
            .order_by("display_order")
        )

        context["active_announcements"] = [
            item.announcement
            for item in active_items
            if item.is_currently_displayed and item.announcement.is_active
        ]
        return context


class NoticeBoardCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = NoticeBoard
    template_name = "communication/noticeboards/noticeboard_form.html"
    fields = [
        "name",
        "board_type",
        "description",
        "location",
        "is_active",
        "refresh_interval",
        "allowed_users",
    ]
    permission_required = "communication.add_noticeboard"

    def form_valid(self, form):
        messages.success(self.request, "Notice board created successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "communication:noticeboard_detail", kwargs={"pk": self.object.pk}
        )


class NoticeBoardUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = NoticeBoard
    template_name = "communication/noticeboards/noticeboard_form.html"
    fields = [
        "name",
        "board_type",
        "description",
        "location",
        "is_active",
        "refresh_interval",
        "allowed_users",
    ]
    permission_required = "communication.change_noticeboard"

    def form_valid(self, form):
        messages.success(self.request, "Notice board updated successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "communication:noticeboard_detail", kwargs={"pk": self.object.pk}
        )


class NoticeBoardDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = NoticeBoard
    template_name = "communication/noticeboards/noticeboard_confirm_delete.html"
    context_object_name = "notice_board"
    permission_required = "communication.delete_noticeboard"
    success_url = reverse_lazy("communication:noticeboard_list")

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Notice board "{self.object.name}" has been deleted successfully!',
        )
        return super().form_valid(form)


class NoticeBoardDetailView(LoginRequiredMixin, DetailView):
    model = NoticeBoard
    template_name = "communication/noticeboards/noticeboard_detail.html"
    context_object_name = "notice_board"

    def get_queryset(self):
        return NoticeBoard.objects.prefetch_related(
            "noticeboarditem_set__announcement", "allowed_users"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all items for this board
        context["board_items"] = (
            self.object.noticeboarditem_set.filter(status="active")
            .select_related("announcement")
            .order_by("display_order")
        )

        # Get available announcements that could be added
        context["available_announcements"] = (
            Announcement.objects.filter(is_published=True, status="active")
            .exclude(noticeboarditem__notice_board=self.object)
            .order_by("-published_at")
        )

        return context


# NoticeBoardItem Management Views
@login_required
@permission_required("communication.change_noticeboard")
def add_announcement_to_board(request, board_pk, announcement_pk):
    """Add an announcement to a notice board"""
    notice_board = get_object_or_404(NoticeBoard, pk=board_pk)
    announcement = get_object_or_404(Announcement, pk=announcement_pk)

    # Check if already exists
    if NoticeBoardItem.objects.filter(
        notice_board=notice_board, announcement=announcement
    ).exists():
        messages.warning(request, "This announcement is already on the notice board.")
    else:
        # Get the highest display order
        max_order = (
            NoticeBoardItem.objects.filter(notice_board=notice_board).aggregate(
                max_order=models.Max("display_order")
            )["max_order"]
            or 0
        )

        NoticeBoardItem.objects.create(
            notice_board=notice_board,
            announcement=announcement,
            display_order=max_order + 1,
        )
        messages.success(
            request, f'Announcement "{announcement.title}" added to notice board.'
        )

    return redirect("communication:noticeboard_detail", pk=board_pk)


@login_required
@permission_required("communication.change_noticeboard")
def remove_announcement_from_board(request, board_pk, item_pk):
    """Remove an announcement from a notice board"""
    notice_board = get_object_or_404(NoticeBoard, pk=board_pk)
    item = get_object_or_404(NoticeBoardItem, pk=item_pk, notice_board=notice_board)

    announcement_title = item.announcement.title
    item.delete()

    # Reorder remaining items
    reorder_notice_board_items(notice_board)

    messages.success(
        request, f'Announcement "{announcement_title}" removed from notice board.'
    )
    return redirect("communication:noticeboard_detail", pk=board_pk)


@login_required
@permission_required("communication.change_noticeboard")
def reorder_notice_board_items(request, board_pk):
    """Reorder notice board items via AJAX"""
    if (
        request.method == "POST"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        notice_board = get_object_or_404(NoticeBoard, pk=board_pk)
        item_orders = request.POST.getlist("item_orders[]")

        try:
            for order_data in item_orders:
                item_id, new_order = order_data.split(":")
                NoticeBoardItem.objects.filter(
                    pk=item_id, notice_board=notice_board
                ).update(display_order=int(new_order))

            return JsonResponse(
                {"success": True, "message": "Items reordered successfully"}
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=400)

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


@login_required
@permission_required("communication.change_noticeboard")
def toggle_notice_board_item(request, item_pk):
    """Toggle active status of a notice board item via AJAX"""
    if (
        request.method == "POST"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        item = get_object_or_404(NoticeBoardItem, pk=item_pk)

        item.is_active = not item.is_active
        item.save()

        return JsonResponse(
            {
                "success": True,
                "is_active": item.is_active,
                "message": f'Item {"activated" if item.is_active else "deactivated"} successfully',
            }
        )

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


def reorder_notice_board_items(notice_board):
    """Helper function to reorder notice board items after deletion"""
    items = NoticeBoardItem.objects.filter(notice_board=notice_board).order_by(
        "display_order"
    )
    for index, item in enumerate(items, start=1):
        item.display_order = index
        item.save()


# Email Template Views
class EmailTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = EmailTemplate
    template_name = "communication/emails/emailtemplate_list.html"
    context_object_name = "email_templates"
    permission_required = "communication.view_emailtemplate"
    paginate_by = 10

    def get_queryset(self):
        return EmailTemplate.objects.filter(is_active=True)


class EmailTemplateCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = EmailTemplate
    template_name = "communication/emails/emailtemplate_form.html"
    fields = [
        "name",
        "template_type",
        "subject",
        "body_html",
        "body_text",
        "language",
        "is_active",
        "variables",
    ]
    permission_required = "communication.add_emailtemplate"

    def form_valid(self, form):
        messages.success(self.request, "Email template created successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("communication:emailtemplate_list")


class EmailTemplateUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = EmailTemplate
    template_name = "communication/emails/emailtemplate_form.html"
    fields = [
        "name",
        "template_type",
        "subject",
        "body_html",
        "body_text",
        "language",
        "is_active",
        "variables",
    ]
    permission_required = "communication.change_emailtemplate"

    def form_valid(self, form):
        messages.success(self.request, "Email template updated successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("communication:emailtemplate_list")


class EmailTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = EmailTemplate
    template_name = "communication/emails/emailtemplate_confirm_delete.html"
    context_object_name = "email_template"
    permission_required = "communication.delete_emailtemplate"
    success_url = reverse_lazy("communication:emailtemplate_list")

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Email template "{self.object.name}" has been deleted successfully!',
        )
        return super().form_valid(form)


@login_required
@permission_required("communication.send_email")
def send_test_email_view(request, pk):
    """Send test email using the template"""
    template = get_object_or_404(EmailTemplate, pk=pk)

    # Get test email address from request or use user's email
    test_email = request.POST.get("test_email") or request.user.email
    if not test_email:
        messages.error(
            request,
            "No test email address provided. Please provide an email address or ensure your user account has an email.",
        )
        return redirect("communication:emailtemplate_detail", pk=pk)

    try:
        from .services import EmailService

        # Prepare test context
        context = {
            "site_name": "School Management System",
            "recipient_name": request.user.get_full_name() or "Test User",
            "user_name": request.user.get_full_name() or "Test User",
            "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "test_mode": True,
        }

        success, message, sent_email = EmailService.send_templated_email(
            template=template,
            recipient_email=test_email,
            context=context,
            recipient_user=request.user,
            sender_user=request.user,
        )

        if success:
            messages.success(
                request,
                f"Test email sent successfully to {test_email} using template: {template.name}",
            )
            if sent_email:
                messages.info(request, f"Email tracked with ID: {sent_email.id}")
        else:
            messages.error(request, f"Failed to send test email: {message}")

    except Exception as e:
        messages.error(request, f"Failed to send test email: {str(e)}")

    return redirect("communication:emailtemplate_list")


@login_required
@permission_required("communication.change_emailtemplate")
def toggle_emailtemplate_status(request, pk):
    """Toggle the active status of an email template via AJAX"""
    if (
        request.method == "POST"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        template = get_object_or_404(EmailTemplate, pk=pk)

        # Toggle the status
        template.is_active = not template.is_active
        template.save()

        return JsonResponse(
            {
                "success": True,
                "is_active": template.is_active,
                "message": f'Template {template.name} {"activated" if template.is_active else "deactivated"} successfully',
            }
        )

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


@login_required
@permission_required("communication.change_emailtemplate")
def bulk_update_template_status(request):
    """Bulk update status (activate/deactivate) templates via AJAX"""
    if (
        request.method == "POST"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        try:
            data = json.loads(request.body)
            template_ids = data.get("template_ids", [])
            is_active = data.get("is_active", False)

            if template_ids:
                updated_count = EmailTemplate.objects.filter(
                    id__in=template_ids
                ).update(is_active=is_active)

                return JsonResponse(
                    {
                        "success": True,
                        "updated_count": updated_count,
                        "message": f'{updated_count} templates {"activated" if is_active else "deactivated"} successfully',
                    }
                )
            else:
                return JsonResponse(
                    {"success": False, "message": "No templates selected"}
                )

        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=400)

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


@login_required
@permission_required("communication.add_emailtemplate")
def duplicate_emailtemplate(request, pk):
    """Duplicate an email template via AJAX"""
    if (
        request.method == "POST"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        template = get_object_or_404(EmailTemplate, pk=pk)

        try:
            # Create a copy of the template
            duplicated_template = EmailTemplate.objects.create(
                name=f"{template.name} (Copy)",
                template_type=template.template_type,
                subject=template.subject,
                body_html=template.body_html,
                body_text=template.body_text,
                language=template.language,
                is_active=False,  # Duplicates are created inactive by default
                variables=template.variables.copy() if template.variables else {},
            )

            return JsonResponse(
                {
                    "success": True,
                    "template_id": str(duplicated_template.id),
                    "message": f'Template "{template.name}" duplicated successfully',
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=400)

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


@login_required
@permission_required("communication.view_emailtemplate")
def export_emailtemplate(request, pk):
    """Export an email template as JSON"""
    template = get_object_or_404(EmailTemplate, pk=pk)

    # Prepare template data for export
    template_data = {
        "name": template.name,
        "template_type": template.template_type,
        "subject": template.subject,
        "body_html": template.body_html,
        "body_text": template.body_text,
        "language": template.language,
        "variables": template.variables,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat(),
    }

    # Return as JSON file download
    response = JsonResponse(template_data, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = (
        f'attachment; filename="email_template_{template.name.replace(" ", "_")}.json"'
    )
    return response


# SMS Views
class SMSTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SMSTemplate
    template_name = "communication/sms/smstemplate_list.html"
    context_object_name = "sms_templates"
    permission_required = "communication.view_smstemplate"

    def get_queryset(self):
        return SMSTemplate.objects.filter(is_active=True)


class SMSTemplateCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = SMSTemplate
    template_name = "communication/sms/smstemplate_form.html"
    fields = ["name", "content", "is_active", "variables"]
    permission_required = "communication.add_smstemplate"

    def form_valid(self, form):
        messages.success(self.request, "SMS template created successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("communication:smstemplate_list")


class SMSTemplateUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = SMSTemplate
    template_name = "communication/sms/smstemplate_form.html"
    fields = ["name", "content", "is_active", "variables"]
    permission_required = "communication.change_smstemplate"

    def form_valid(self, form):
        messages.success(self.request, "SMS template updated successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("communication:smstemplate_list")


class SMSTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = SMSTemplate
    template_name = "communication/sms/smstemplate_confirm_delete.html"
    context_object_name = "sms_template"
    permission_required = "communication.delete_smstemplate"
    success_url = reverse_lazy("communication:smstemplate_list")

    def form_valid(self, form):
        messages.success(
            self.request,
            f'SMS template "{self.object.name}" has been deleted successfully!',
        )
        return super().form_valid(form)


# Dashboard and Analytics Views
@login_required
def communication_dashboard(request):
    """Communication dashboard with statistics"""
    user = request.user

    # Basic statistics
    context = {
        "unread_notification_count": RealTimeNotification.get_unread_count(user),
        "chat_room_count": ChatRoom.objects.filter(
            members=user, is_active=True
        ).count(),
        "announcement_count": Announcement.objects.filter(
            is_published=True, status="active"
        ).count(),
    }

    # Add teacher/admin specific stats
    if user.has_perm("communication.view_analytics"):
        context.update(
            {
                "total_notifications": RealTimeNotification.objects.count(),
                "total_chat_messages": ChatMessage.objects.count(),
                "total_announcements": Announcement.objects.count(),
                "active_chat_rooms": ChatRoom.objects.filter(is_active=True).count(),
            }
        )

    return render(request, "communication/dashboard/dashboard.html", context)


# Utility function
def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# Bulk Action Views
@login_required
@permission_required("communication.change_announcement")
def bulk_publish_announcements(request):
    """Bulk publish selected announcements"""
    if request.method == "POST":
        announcement_ids = request.POST.getlist("announcement_ids")

        if announcement_ids:
            updated = Announcement.objects.filter(
                id__in=announcement_ids,
                author=request.user,  # Users can only publish their own announcements
            ).update(is_published=True, published_at=timezone.now())

            messages.success(
                request, f"Successfully published {updated} announcements."
            )
        else:
            messages.warning(request, "No announcements selected.")

    return redirect("communication:announcement_list")


@login_required
@permission_required("communication.delete_announcement")
def bulk_delete_announcements(request):
    """Bulk delete selected announcements"""
    if request.method == "POST":
        announcement_ids = request.POST.getlist("announcement_ids")

        if announcement_ids:
            # Users can only delete their own announcements unless they have admin permission
            if request.user.has_perm("communication.admin_delete_announcement"):
                # Admins can delete any announcements
                deleted_count, _ = Announcement.objects.filter(
                    id__in=announcement_ids
                ).delete()
            else:
                # Regular users can only delete their own announcements
                deleted_count, _ = Announcement.objects.filter(
                    id__in=announcement_ids, author=request.user
                ).delete()

            messages.success(
                request, f"Successfully deleted {deleted_count} announcements."
            )
        else:
            messages.warning(request, "No announcements selected.")

    return redirect("communication:announcement_list")


@login_required
@permission_required("communication.delete_emailtemplate")
def bulk_delete_templates(request):
    """Bulk delete selected email templates"""
    if request.method == "POST":
        template_ids = request.POST.getlist("template_ids")

        if template_ids:
            # Delete templates
            deleted_count, _ = EmailTemplate.objects.filter(
                id__in=template_ids
            ).delete()

            messages.success(
                request, f"Successfully deleted {deleted_count} email templates."
            )
        else:
            messages.warning(request, "No templates selected.")

    return redirect("communication:emailtemplate_list")


# Parent Calendar View
class ParentCalendarView(LoginRequiredMixin, View):
    """Calendar view for parents showing events, holidays, and important dates."""

    def get(self, request):
        user = request.user

        # Check if user is a parent
        if not user.user_roles.filter(role__role_type="parent").exists():
            messages.error(request, "Access denied. This page is for parents only.")
            return redirect("users:dashboard")

        # Get current session
        from apps.academics.models import AcademicSession, Holiday

        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Get holidays for current session
        holidays = (
            Holiday.objects.filter(academic_session=current_session).order_by("date")
            if current_session
            else []
        )

        # Get events from announcements (EVENT and HOLIDAY types)
        events = Announcement.objects.filter(
            is_published=True,
            status="active",
            announcement_type__in=["event", "holiday"],
        ).order_by("published_at")

        # Filter events for parents
        from apps.users.models import ParentStudentRelationship

        children_classes = (
            ParentStudentRelationship.objects.filter(parent=user, status="active")
            .values_list("student__enrollments__class_enrolled", flat=True)
            .distinct()
        )

        events = events.filter(
            Q(target_audience="all")
            | Q(target_audience="parents")
            | Q(specific_users=user)
            | Q(specific_classes__in=children_classes)
        ).distinct()

        # Get urgent announcements for emergency alerts
        urgent_alerts = (
            Announcement.objects.filter(
                is_published=True, status="active", priority="urgent"
            )
            .filter(
                Q(target_audience="all")
                | Q(target_audience="parents")
                | Q(specific_users=user)
                | Q(specific_classes__in=children_classes)
            )
            .distinct()
            .order_by("-published_at")[:5]
        )

        context = {
            "current_session": current_session,
            "holidays": holidays,
            "events": events,
            "urgent_alerts": urgent_alerts,
            "today": timezone.now().date(),
        }

        return render(request, "communication/calendar/parent_calendar.html", context)


# ===== NOTIFICATION VIEWS =====


class NotificationListView(LoginRequiredMixin, ListView):
    """
    View for listing all notifications for the current user
    """

    model = RealTimeNotification
    template_name = "communication/notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return RealTimeNotification.objects.filter(
            recipient=self.request.user
        ).order_by("-created_at")


class UnreadNotificationListView(LoginRequiredMixin, ListView):
    """
    View for listing only unread notifications
    """

    model = RealTimeNotification
    template_name = "communication/notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return RealTimeNotification.objects.filter(
            recipient=self.request.user, is_read=False
        ).order_by("-created_at")


class NotificationDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying a single notification and marking it as read
    """

    model = RealTimeNotification
    template_name = "communication/notifications/notification_detail.html"
    context_object_name = "notification"

    def get_queryset(self):
        return RealTimeNotification.objects.filter(recipient=self.request.user)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Mark notification as read when viewed
        if not self.object.is_read:
            self.object.mark_as_read()
        return response


@login_required
def mark_notification_read(request, pk):
    """
    Mark a specific notification as read
    """
    notification = get_object_or_404(
        RealTimeNotification, pk=pk, recipient=request.user
    )

    if not notification.is_read:
        notification.mark_as_read()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True})

    return redirect("communication:notification_list")


@login_required
def mark_all_notifications_read(request):
    """
    Mark all notifications as read for the current user
    """
    RealTimeNotification.mark_all_read(request.user)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {"success": True, "message": "All notifications marked as read"}
        )

    return redirect("communication:notification_list")


@login_required
def delete_notification(request, pk):
    """
    Delete a specific notification
    """
    notification = get_object_or_404(
        RealTimeNotification, pk=pk, recipient=request.user
    )
    notification.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True})

    return redirect("communication:notification_list")


@login_required
def clear_all_notifications(request):
    """
    Delete all notifications for the current user
    """
    RealTimeNotification.objects.filter(recipient=request.user).delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "All notifications cleared"})

    return redirect("communication:notification_list")


@login_required
def get_unread_notification_count(request):
    """
    API endpoint to get unread notification count for AJAX requests
    """
    unread_count = RealTimeNotification.get_unread_count(request.user)

    return JsonResponse({"unread_count": unread_count})


@login_required
def notification_preferences(request):
    """
    View for managing notification preferences
    """
    # This would integrate with user profile settings
    # For now, it's a placeholder that can be extended
    return render(request, "communication/notifications/preferences.html")


class NotificationAPIView(LoginRequiredMixin, View):
    """
    API view for notification operations
    """

    def get(self, request):
        """
        Get notifications with filtering and pagination
        """
        # Get filter parameters
        notification_type = request.GET.get("type")
        priority = request.GET.get("priority")
        is_read = request.GET.get("is_read")
        page = request.GET.get("page", 1)

        # Base queryset
        notifications = RealTimeNotification.objects.filter(recipient=request.user)

        # Apply filters
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)

        if priority:
            notifications = notifications.filter(priority=priority)

        if is_read is not None:
            is_read_bool = is_read.lower() == "true"
            notifications = notifications.filter(is_read=is_read_bool)

        # Order and paginate
        notifications = notifications.order_by("-created_at")
        paginator = Paginator(notifications, 20)
        page_obj = paginator.get_page(page)

        # Prepare response data
        notifications_data = []
        for notification in page_obj:
            notifications_data.append(
                {
                    "id": str(notification.id),
                    "title": notification.title,
                    "message": notification.message,
                    "type": notification.notification_type,
                    "priority": notification.priority,
                    "is_read": notification.is_read,
                    "created_at": notification.created_at.isoformat(),
                    "action_url": notification.action_url,
                }
            )

        return JsonResponse(
            {
                "notifications": notifications_data,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_count": paginator.count,
            }
        )


def create_notification(
    user,
    title,
    message,
    notification_type="info",
    priority="medium",
    action_url="",
    related_model="",
    related_object_id="",
    expires_at=None,
):
    """
    Utility function to create notifications programmatically
    """
    # Resolve institution for CoreBaseModel requirement
    from django.apps import apps

    Institution = apps.get_model("core", "Institution")
    inst = None
    try:
        primary = getattr(user, "institution_memberships", None)
        if primary and primary.filter(is_primary=True).exists():
            inst = primary.filter(is_primary=True).first().institution
        elif getattr(user, "institutions", None) and user.institutions.exists():
            inst = user.institutions.first()
    except Exception:
        inst = None

    if not inst:
        inst = Institution.objects.first()

    notification = RealTimeNotification.objects.create(
        recipient=user,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        action_url=action_url,
        expires_at=expires_at,
        institution=inst,
    )
    return notification


# ===== REAL-TIME NOTIFICATION VIEWS =====


class RealTimeNotificationListView(LoginRequiredMixin, ListView):
    """
    View for listing real-time notifications for the current user
    """

    model = RealTimeNotification
    template_name = "communication/notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return RealTimeNotification.objects.filter(
            recipient=self.request.user
        ).order_by("-created_at")


class RealTimeNotificationDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying a single real-time notification and marking it as read
    """

    model = RealTimeNotification
    template_name = "communication/notifications/notification_detail.html"
    context_object_name = "notification"

    def get_queryset(self):
        return RealTimeNotification.objects.filter(recipient=self.request.user)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Mark notification as read when viewed
        if not self.object.is_read:
            self.object.mark_as_read()
        return response


@login_required
def realtime_notification_preferences(request):
    """
    View for managing real-time notification preferences
    """
    try:
        preferences = NotificationPreference.objects.get(user=request.user)
    except NotificationPreference.DoesNotExist:
        preferences = NotificationPreference.objects.create(user=request.user)

    if request.method == "POST":
        # Update preferences based on form data
        preferences.enable_realtime = request.POST.get("enable_realtime") == "on"
        preferences.message_notifications = (
            request.POST.get("message_notifications") == "on"
        )
        preferences.assignment_notifications = (
            request.POST.get("assignment_notifications") == "on"
        )
        preferences.grade_notifications = (
            request.POST.get("grade_notifications") == "on"
        )
        preferences.announcement_notifications = (
            request.POST.get("announcement_notifications") == "on"
        )
        preferences.event_notifications = (
            request.POST.get("event_notifications") == "on"
        )
        preferences.alert_notifications = (
            request.POST.get("alert_notifications") == "on"
        )
        preferences.email_notifications = (
            request.POST.get("email_notifications") == "on"
        )
        preferences.push_notifications = request.POST.get("push_notifications") == "on"
        preferences.sms_notifications = request.POST.get("sms_notifications") == "on"
        preferences.quiet_hours_enabled = (
            request.POST.get("quiet_hours_enabled") == "on"
        )
        preferences.sound_enabled = request.POST.get("sound_enabled") == "on"

        if request.POST.get("quiet_hours_start"):
            preferences.quiet_hours_start = request.POST.get("quiet_hours_start")
        if request.POST.get("quiet_hours_end"):
            preferences.quiet_hours_end = request.POST.get("quiet_hours_end")
        if request.POST.get("sound_volume"):
            preferences.sound_volume = int(request.POST.get("sound_volume"))

        preferences.save()
        messages.success(request, "Notification preferences updated successfully!")

    return render(
        request,
        "communication/notifications/preferences.html",
        {"preferences": preferences},
    )


# ===== CHAT VIEWS =====


class ChatRoomListView(LoginRequiredMixin, ListView):
    """
    View for listing chat rooms the user has access to
    """

    model = ChatRoom
    template_name = "communication/chat/chat_room_list.html"
    context_object_name = "chat_rooms"
    paginate_by = 20

    def get_queryset(self):
        return ChatRoom.objects.filter(
            members=self.request.user, is_active=True
        ).order_by("-updated_at")


class ChatRoomDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying a chat room and its messages
    """

    model = ChatRoom
    template_name = "communication/chat/chat_room_detail.html"
    context_object_name = "chat_room"

    def get_queryset(self):
        return ChatRoom.objects.filter(members=self.request.user, is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get recent messages (last 50)
        context["recent_messages"] = self.object.messages.order_by("-created_at")[:50][
            ::-1
        ]
        # Get other members
        context["other_members"] = self.object.members.exclude(id=self.request.user.id)
        return context


class ChatRoomCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating a new chat room
    """

    model = ChatRoom
    template_name = "communication/chat/room_form.html"
    fields = ["name", "room_type", "description", "members", "admins"]

    def form_valid(self, form):
        form.instance.save()
        # Add creator as admin and member
        form.instance.members.add(self.request.user)
        form.instance.admins.add(self.request.user)
        messages.success(
            self.request, f'Chat room "{form.instance.name}" created successfully!'
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "communication:chat_room_detail", kwargs={"pk": self.object.pk}
        )


@login_required
def send_chat_message(request, room_pk):
    """
    Send a message to a chat room via AJAX
    """
    if (
        request.method == "POST"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        room = get_object_or_404(ChatRoom, pk=room_pk, members=request.user)

        content = request.POST.get("content", "").strip()
        message_type = request.POST.get("message_type", "text")

        if content:
            message = ChatMessage.objects.create(
                room=room,
                sender=request.user,
                content=content,
                message_type=message_type,
            )

            # Update room's updated_at
            room.save(update_fields=["updated_at"])

            return JsonResponse(
                {
                    "success": True,
                    "message_id": str(message.id),
                    "message": {
                        "id": str(message.id),
                        "content": message.content,
                        "sender": message.sender.get_full_name(),
                        "created_at": message.created_at.isoformat(),
                        "message_type": message.message_type,
                    },
                }
            )

        return JsonResponse(
            {"success": False, "message": "Message content is required"}
        )

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


@login_required
def get_chat_messages(request, room_pk):
    """
    Get messages for a chat room via AJAX
    """
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        room = get_object_or_404(ChatRoom, pk=room_pk, members=request.user)

        # Get messages after a certain timestamp if provided
        after_timestamp = request.GET.get("after")
        if after_timestamp:
            messages_queryset = room.messages.filter(created_at__gt=after_timestamp)
        else:
            messages_queryset = room.messages.all()

        messages_data = []
        for message in messages_queryset.order_by("created_at"):
            messages_data.append(
                {
                    "id": str(message.id),
                    "content": message.content,
                    "sender": message.sender.get_full_name(),
                    "sender_id": str(message.sender.id),
                    "created_at": message.created_at.isoformat(),
                    "message_type": message.message_type,
                    "is_edited": message.is_edited,
                }
            )

        return JsonResponse({"success": True, "messages": messages_data})

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


@login_required
def mark_chat_messages_read(request, room_pk):
    """
    Mark all messages in a chat room as read for the current user
    """
    if (
        request.method == "POST"
        and request.headers.get("x-requested-with") == "XMLHttpRequest"
    ):
        room = get_object_or_404(ChatRoom, pk=room_pk, members=request.user)

        # Mark all unread messages as read
        unread_messages = room.messages.exclude(read_by=request.user)
        for message in unread_messages:
            message.read_by.add(request.user)

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "message": "Invalid request"}, status=400)


# ===== MESSAGE VIEWS =====


class MessageCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating and sending messages
    """

    model = Message
    form_class = MessageForm
    template_name = "communication/messages/message_form.html"

    def get_form_kwargs(self):
        """Pass request to form"""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        """Handle form submission"""
        message = (
            form.save()
        )  # This handles recipients creation in the form's save method
        messages.success(
            self.request,
            f'Message "{message.subject}" sent successfully to {message.recipients_count} recipient(s)!',
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("communication:inbox")


# ===== UTILITY FUNCTIONS =====

# Signal handlers for automatic notifications
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def send_welcome_notification(sender, instance, created, **kwargs):
    """
    Send welcome notification when a new user is created
    """
    if created:
        create_notification(
            instance,
            title="Welcome to the System!",
            message="Thank you for joining us. Please complete your profile to get started.",
            notification_type="info",
            priority="low",
        )


# ===== PUBLIC NOTICE BOARD VIEWS =====


def public_noticeboard_portal(request):
    """
    Public noticeboard portal for guests and unregistered users
    Shows public notice boards and their announcements
    """
    # Get all public notice boards (ones that allow public access)
    public_noticeboards = (
        NoticeBoard.objects.filter(
            is_active=True,
            status="active",
            board_type="public",  # Assuming there's a board_type field or similar
        )
        .prefetch_related("noticeboarditem_set__announcement")
        .order_by("name")
    )

    # Collect all active announcements from public boards
    public_announcements = []
    for board in public_noticeboards:
        # Get active items for this board
        active_items = board.noticeboarditem_set.filter(
            is_active=True, status="active"
        ).select_related("announcement")

        for item in active_items:
            if item.is_currently_displayed and item.announcement.is_active:
                announcement_data = {
                    "announcement": item.announcement,
                    "board": board,
                    "display_order": item.display_order,
                }
                public_announcements.append(announcement_data)

    # Sort announcements by urgency, then by pinned status, then by display order
    public_announcements.sort(
        key=lambda x: (
            (
                0
                if x["announcement"].priority == "urgent"
                else 1 if x["announcement"].is_pinned else 2
            ),
            x["display_order"],
        ),
        reverse=True,
    )

    # Group announcements by board for display
    announcements_by_board = {}
    for data in public_announcements:
        board_id = data["board"].id
        if board_id not in announcements_by_board:
            announcements_by_board[board_id] = {
                "board": data["board"],
                "announcements": [],
            }
        announcements_by_board[board_id]["announcements"].append(data["announcement"])

    context = {
        "public_noticeboards": public_noticeboards,
        "announcements_by_board": announcements_by_board,
        "total_announcements": len(public_announcements),
        "is_public_view": True,
    }

    return render(request, "communication/noticeboards/public_portal.html", context)
