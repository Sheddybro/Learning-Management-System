from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    FormView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count, Case, When, IntegerField
from django.views import View
from django.core.paginator import Paginator

from apps.core.mixins import InstitutionPermissionMixin
from apps.core.middleware import get_user_accessible_institutions

from .models import (
    HelpCenterArticle,
    Resource,
    FAQ,
    ContactSubmission,
    LegalDocument,
    Category,
    SupportCase,
    CaseUpdate,
    CaseParticipant,
    CaseAttachment,
)
from .forms import (
    ContactForm,
    HelpCenterArticleForm,
    ResourceForm,
    FAQForm,
    SupportCaseForm,
    CaseUpdateForm,
    CaseParticipantForm,
    CaseAttachmentForm,
    CaseSearchForm,
    BulkCaseActionForm,
    CaseEscalationForm,
)


class SupportStaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user has support staff permissions.
    """

    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.has_perm("support.change_supportcase")
            or self.request.user.has_perm("support.view_supportcase")
            or self.request.user.user_roles.filter(
                role__role_type__in=[
                    "support",
                    "admin",
                    "principal",
                    "school_admin",
                    "super_admin",
                ]
            ).exists()
        )


class CaseAccessMixin(UserPassesTestMixin):
    """
    Mixin to ensure user can access specific case.
    """

    def test_func(self):
        if not self.request.user.is_authenticated:
            return False

        # Support staff can access all cases
        if (
            self.request.user.has_perm("support.change_supportcase")
            or self.request.user.has_perm("support.view_supportcase")
            or self.request.user.user_roles.filter(
                role__role_type__in=[
                    "support",
                    "admin",
                    "principal",
                    "school_admin",
                    "super_admin",
                ]
            ).exists()
        ):
            return True

        # Case participants can access their cases
        case_id = self.kwargs.get("pk")
        if case_id:
            return CaseParticipant.objects.filter(
                case_id=case_id, user=self.request.user, is_active=True
            ).exists()

        return False


# ===== EXISTING SUPPORT VIEWS =====


class ContactSubmissionListView(InstitutionPermissionMixin, ListView):
    model = ContactSubmission
    template_name = "support/tickets/list.html"
    context_object_name = "submissions"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        filter_by = self.request.GET.get("filter", "all")
        if filter_by == "resolved":
            queryset = queryset.filter(is_resolved=True)
        elif filter_by == "unresolved":
            queryset = queryset.filter(is_resolved=False)
        return queryset.order_by("-created_at")


class ContactSubmissionDetailView(
    LoginRequiredMixin, SupportStaffRequiredMixin, DetailView
):
    model = ContactSubmission
    template_name = "support/tickets/detail.html"
    context_object_name = "submission"


class ContactSubmissionUpdateView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = ContactSubmission
    template_name = "support/tickets/update.html"
    fields = ["is_resolved", "resolution_notes"]
    success_message = "Submission status updated successfully."

    def get_success_url(self):
        return reverse_lazy("support:ticket_detail", kwargs={"pk": self.object.pk})


def legal_documents_list(request):
    """List all active legal documents."""
    # Scope legal documents to user's accessible institutions for non-superusers
    if request.user.is_authenticated and not request.user.is_superuser:
        accessible_insts = get_user_accessible_institutions(request.user)
        documents = LegalDocument.objects.filter(
            is_active=True, institution__in=accessible_insts
        ).order_by("document_type")
    else:
        documents = LegalDocument.objects.filter(is_active=True).order_by(
            "document_type"
        )
    context = {"documents": documents}
    return render(request, "support/legal/legal_documents.html", context)


class HelpCenterArticleListView(ListView):
    model = HelpCenterArticle
    template_name = "support/articles/list.html"
    context_object_name = "articles"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_published=True)
        category_slug = self.kwargs.get("category_slug")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True)

        # Add statistics for the template
        all_articles = HelpCenterArticle.objects.filter(is_published=True)
        context["total_articles"] = all_articles.count()
        context["total_categories"] = Category.objects.filter(is_active=True).count()
        context["general_articles"] = all_articles.filter(category__isnull=True).count()

        return context


class HelpCenterArticleCreateView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, CreateView
):
    model = HelpCenterArticle
    form_class = HelpCenterArticleForm
    template_name = "support/articles/form.html"
    success_url = reverse_lazy("support:article_list")
    success_message = "Article created successfully."


class HelpCenterArticleUpdateView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = HelpCenterArticle
    form_class = HelpCenterArticleForm
    template_name = "support/articles/form.html"
    success_url = reverse_lazy("support:article_list")
    success_message = "Article updated successfully."


class HelpCenterArticleDeleteView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = HelpCenterArticle
    template_name = "support/articles/confirm_delete.html"
    success_url = reverse_lazy("support:article_list")
    success_message = "Article deleted successfully."


class HelpCenterArticleDetailView(DetailView):
    model = HelpCenterArticle
    template_name = "support/articles/detail.html"
    context_object_name = "article"

    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.views += 1
        obj.save()
        return obj


class ResourceListView(ListView):
    model = Resource
    template_name = "support/resources/list.html"
    context_object_name = "resources"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_published=True)
        resource_type = self.request.GET.get("type")
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add statistics for the template
        all_resources = Resource.objects.filter(is_published=True)
        context["total_resources"] = all_resources.count()
        context["resource_types"] = dict(Resource.ResourceType.choices)

        # Create a list of resource type statistics for easier template access
        resource_type_stats = []
        for resource_type, type_label in Resource.ResourceType.choices:
            count = all_resources.filter(resource_type=resource_type).count()
            if count > 0:
                resource_type_stats.append(
                    {"type": resource_type, "label": type_label, "count": count}
                )
        context["resource_type_stats"] = resource_type_stats

        return context


class ResourceCreateView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, CreateView
):
    model = Resource
    form_class = ResourceForm
    template_name = "support/resources/form.html"
    success_url = reverse_lazy("support:resource_list")
    success_message = "Resource created successfully."


class ResourceUpdateView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = Resource
    form_class = ResourceForm
    template_name = "support/resources/form.html"
    success_url = reverse_lazy("support:resource_list")
    success_message = "Resource updated successfully."


class ResourceDeleteView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = Resource
    template_name = "support/resources/confirm_delete.html"
    success_url = reverse_lazy("support:resource_list")
    success_message = "Resource deleted successfully."


class ResourceDetailView(DetailView):
    model = Resource
    template_name = "support/resources/detail.html"
    context_object_name = "resource"

    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)


class FAQListView(ListView):
    model = FAQ
    template_name = "support/faq/list.html"
    context_object_name = "faqs"
    queryset = FAQ.objects.filter(is_published=True).order_by("order")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(faqs__isnull=False).distinct()
        return context


class FAQCreateView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, CreateView
):
    model = FAQ
    form_class = FAQForm
    template_name = "support/faq/form.html"
    success_url = reverse_lazy("support:faq_list")
    success_message = "FAQ created successfully."


class FAQUpdateView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, UpdateView
):
    model = FAQ
    form_class = FAQForm
    template_name = "support/faq/form.html"
    success_url = reverse_lazy("support:faq_list")
    success_message = "FAQ updated successfully."


class FAQDeleteView(
    LoginRequiredMixin, SupportStaffRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = FAQ
    template_name = "support/faq/confirm_delete.html"
    success_url = reverse_lazy("support:faq_list")
    success_message = "FAQ deleted successfully."


class ContactSupportView(FormView):
    template_name = "support/contact/support.html"
    form_class = ContactForm
    success_url = reverse_lazy("support:contact_success")

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            "Your message has been sent successfully. We will get back to you soon.",
        )
        return super().form_valid(form)


def contact_success_view(request):
    return render(request, "support/contact/success.html")


class LegalDocumentDetailView(DetailView):
    model = LegalDocument
    template_name = "support/legal/document_detail.html"
    context_object_name = "document"

    def get_object(self, queryset=None):
        document_type = self.kwargs.get("document_type")
        return get_object_or_404(
            LegalDocument, document_type=document_type, is_active=True
        )


# ===== STUDENT SUPPORT TEAM COLLABORATION VIEWS =====


class SupportCaseListView(InstitutionPermissionMixin, ListView):
    """
    List view for support cases with filtering and search.
    """

    model = SupportCase
    template_name = "support/cases/case_list.html"
    context_object_name = "cases"
    paginate_by = 15

    def get_queryset(self):
        queryset = SupportCase.objects.select_related(
            "student", "reported_by", "category"
        ).prefetch_related("assigned_to", "tags")

        # Permission-based filtering
        user = self.request.user
        if not user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists():
            # Regular users can only see cases they're participants in
            queryset = queryset.filter(
                Q(participants__user=user, participants__is_active=True)
            ).distinct()

        # Apply search and filters
        search_form = CaseSearchForm(self.request.GET)
        if search_form.is_valid():
            search_query = search_form.cleaned_data.get("search_query")
            case_type = search_form.cleaned_data.get("case_type")
            priority = search_form.cleaned_data.get("priority")
            status = search_form.cleaned_data.get("status")
            assigned_to_me = search_form.cleaned_data.get("assigned_to_me")
            overdue_only = search_form.cleaned_data.get("overdue_only")
            date_from = search_form.cleaned_data.get("date_from")
            date_to = search_form.cleaned_data.get("date_to")

            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query)
                    | Q(description__icontains=search_query)
                    | Q(student__user__first_name__icontains=search_query)
                    | Q(student__user__last_name__icontains=search_query)
                    | Q(case_number__icontains=search_query)
                )

            if case_type:
                queryset = queryset.filter(case_type=case_type)
            if priority:
                queryset = queryset.filter(priority=priority)
            if status:
                queryset = queryset.filter(status=status)
            if assigned_to_me:
                queryset = queryset.filter(
                    participants__user=user, participants__is_active=True
                )
            if overdue_only:
                queryset = queryset.filter(
                    Q(estimated_resolution_time__isnull=False)
                    & Q(
                        created_at__lt=timezone.now() - timezone.timedelta(hours=1)
                    )  # Simplified overdue check
                )
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset.order_by("-created_at", "priority")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = CaseSearchForm(self.request.GET)

        # Statistics for support staff
        user = self.request.user
        if user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists():
            # Scope stats to institutions the user can access
            if user.is_superuser:
                all_cases = SupportCase.objects.all()
            else:
                accessible_insts = get_user_accessible_institutions(user)
                all_cases = SupportCase.objects.filter(institution__in=accessible_insts)

            context["stats"] = {
                "total_cases": all_cases.count(),
                "open_cases": all_cases.filter(status="open").count(),
                "in_progress_cases": all_cases.filter(status="in_progress").count(),
                "overdue_cases": sum(1 for case in all_cases if case.is_overdue),
                "urgent_cases": all_cases.filter(
                    priority__in=["urgent", "critical"]
                ).count(),
            }

        return context


class SupportCaseDetailView(LoginRequiredMixin, CaseAccessMixin, DetailView):
    """
    Detail view for support cases with full collaboration features.
    """

    model = SupportCase
    template_name = "support/cases/case_detail.html"
    context_object_name = "case"

    def get_queryset(self):
        return SupportCase.objects.select_related(
            "student", "reported_by", "category", "resolved_by"
        ).prefetch_related(
            "assigned_to", "tags", "updates__user", "attachments__uploaded_by"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Forms for collaboration
        context["update_form"] = CaseUpdateForm()
        context["attachment_form"] = CaseAttachmentForm()
        context["participant_form"] = CaseParticipantForm()

        # Check permissions
        user = self.request.user
        context["can_edit"] = user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists()
        context["is_participant"] = CaseParticipant.objects.filter(
            case=self.object, user=user, is_active=True
        ).exists()
        context["can_escalate"] = (
            context["can_edit"]
            and not self.object.is_escalated
            and self.object.status not in ["resolved", "closed"]
        )

        return context


class SupportCaseCreateView(LoginRequiredMixin, CreateView):
    """
    Create view for new support cases.
    """

    model = SupportCase
    form_class = SupportCaseForm
    template_name = "support/cases/case_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        # Set the student based on URL parameter or current user context
        student_id = self.kwargs.get("student_id")
        if student_id:
            from apps.academics.models import Student

            form.instance.student = get_object_or_404(Student, pk=student_id)

        messages.success(self.request, "Support case created successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("support:case_detail", kwargs={"pk": self.object.pk})


class SupportCaseUpdateView(LoginRequiredMixin, CaseAccessMixin, UpdateView):
    """
    Update view for support cases.
    """

    model = SupportCase
    form_class = SupportCaseForm
    template_name = "support/cases/case_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Support case updated successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("support:case_detail", kwargs={"pk": self.object.pk})


class SupportCaseDeleteView(LoginRequiredMixin, SupportStaffRequiredMixin, DeleteView):
    """
    Delete view for support cases.
    """

    model = SupportCase
    template_name = "support/cases/case_confirm_delete.html"
    success_url = reverse_lazy("support:case_list")

    def form_valid(self, form):
        messages.success(
            self.request, f'Case "{self.object.title}" has been deleted successfully!'
        )
        return super().form_valid(form)


# ===== AJAX VIEWS FOR COLLABORATION =====


@login_required
def add_case_update(request, pk):
    """
    AJAX view to add updates to cases.
    """
    case = get_object_or_404(SupportCase, pk=pk)

    # Check permissions
    if not CaseAccessMixin().test_func(request):
        return JsonResponse({"success": False, "message": "Permission denied"})

    if request.method == "POST":
        form = CaseUpdateForm(request.POST, request.FILES, case=case, user=request.user)
        if form.is_valid():
            update = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Update added successfully",
                    "update_id": update.pk,
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Form validation failed",
                    "errors": form.errors,
                }
            )

    return JsonResponse({"success": False, "message": "Invalid request method"})


@login_required
def add_case_attachment(request, pk):
    """
    AJAX view to add attachments to cases.
    """
    case = get_object_or_404(SupportCase, pk=pk)

    # Check permissions
    if not CaseAccessMixin().test_func(request):
        return JsonResponse({"success": False, "message": "Permission denied"})

    if request.method == "POST":
        form = CaseAttachmentForm(
            request.POST, request.FILES, case=case, user=request.user
        )
        if form.is_valid():
            attachment = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Attachment added successfully",
                    "attachment_id": attachment.pk,
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Form validation failed",
                    "errors": form.errors,
                }
            )

    return JsonResponse({"success": False, "message": "Invalid request method"})


@login_required
def add_case_participant(request, pk):
    """
    AJAX view to add participants to cases.
    """
    case = get_object_or_404(SupportCase, pk=pk)

    # Check permissions (only support staff can manage participants)
    if not request.user.user_roles.filter(
        role__role_type__in=["support", "admin", "principal", "super_admin"]
    ).exists():
        return JsonResponse({"success": False, "message": "Permission denied"})

    if request.method == "POST":
        form = CaseParticipantForm(request.POST, case=case)
        if form.is_valid():
            participant = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Participant added successfully",
                    "participant_id": participant.pk,
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Form validation failed",
                    "errors": form.errors,
                }
            )

    return JsonResponse({"success": False, "message": "Invalid request method"})


@login_required
def remove_case_participant(request, pk, participant_pk):
    """
    AJAX view to remove participants from cases.
    """
    case = get_object_or_404(SupportCase, pk=pk)
    participant = get_object_or_404(CaseParticipant, pk=participant_pk, case=case)

    # Check permissions
    if not request.user.user_roles.filter(
        role__role_type__in=["support", "admin", "principal", "super_admin"]
    ).exists():
        return JsonResponse({"success": False, "message": "Permission denied"})

    if request.method == "POST":
        participant.is_active = False
        participant.save()
        return JsonResponse(
            {"success": True, "message": "Participant removed successfully"}
        )

    return JsonResponse({"success": False, "message": "Invalid request method"})


@login_required
def update_case_status(request, pk):
    """
    AJAX view to update case status.
    """
    case = get_object_or_404(SupportCase, pk=pk)

    # Check permissions
    if not request.user.user_roles.filter(
        role__role_type__in=["support", "admin", "principal", "super_admin"]
    ).exists():
        return JsonResponse({"success": False, "message": "Permission denied"})

    if request.method == "POST":
        new_status = request.POST.get("status")
        resolution = request.POST.get("resolution", "")

        if new_status in dict(SupportCase.CaseStatus.choices):
            case.status = new_status
            if new_status in ["resolved", "closed"]:
                case.resolved_by = request.user
                case.resolution = resolution
            case.save()

            # Create status update
            CaseUpdate.objects.create(
                case=case,
                user=request.user,
                update_type="status_change",
                content=f"Status changed to {case.get_status_display()}",
                is_private=False,
            )

            return JsonResponse(
                {"success": True, "message": "Case status updated successfully"}
            )
        else:
            return JsonResponse({"success": False, "message": "Invalid status"})

    return JsonResponse({"success": False, "message": "Invalid request method"})


@login_required
def escalate_case(request, pk):
    """
    View to escalate support cases.
    """
    case = get_object_or_404(SupportCase, pk=pk)

    # Check permissions
    if not request.user.user_roles.filter(
        role__role_type__in=["support", "admin", "principal", "super_admin"]
    ).exists():
        messages.error(request, "Permission denied")
        return redirect("support:case_detail", pk=pk)

    if request.method == "POST":
        form = CaseEscalationForm(request.POST)
        if form.is_valid():
            escalate_to = form.cleaned_data["escalate_to"]
            escalation_reason = form.cleaned_data["escalation_reason"]

            case.is_escalated = True
            case.escalated_to = escalate_to
            case.escalation_reason = escalation_reason
            case.save()

            # Create escalation update
            CaseUpdate.objects.create(
                case=case,
                user=request.user,
                update_type="escalation",
                content=f"Case escalated to {escalate_to.get_full_name()}: {escalation_reason}",
                is_private=False,
            )

            messages.success(request, "Case escalated successfully")
            return redirect("support:case_detail", pk=pk)
    else:
        form = CaseEscalationForm()

    return render(
        request, "support/cases/case_escalate.html", {"case": case, "form": form}
    )


@login_required
def bulk_case_actions(request):
    """
    View for bulk actions on support cases.
    """
    # Check permissions
    if not request.user.user_roles.filter(
        role__role_type__in=["support", "admin", "principal", "super_admin"]
    ).exists():
        messages.error(request, "Permission denied")
        return redirect("support:case_list")

    if request.method == "POST":
        form = BulkCaseActionForm(request.POST)
        if form.is_valid():
            case_ids = request.POST.getlist("case_ids")
            action = form.cleaned_data["action"]

            cases = SupportCase.objects.filter(id__in=case_ids)
            updated_count = 0

            if action == "status_change":
                new_status = form.cleaned_data["new_status"]
                for case in cases:
                    case.status = new_status
                    case.save()
                    updated_count += 1

            elif action == "assign_participants":
                users = form.cleaned_data["assign_users"]
                for case in cases:
                    for user in users:
                        case.add_participant(user, role="member")
                    updated_count += 1

            elif action == "add_tags":
                tags = form.cleaned_data["add_tags"]
                for case in cases:
                    case.tags.add(*tags)
                    updated_count += 1

            elif action == "set_priority":
                new_priority = form.cleaned_data["new_priority"]
                for case in cases:
                    case.priority = new_priority
                    case.save()
                    updated_count += 1

            elif action == "close_cases":
                resolution_note = form.cleaned_data["resolution_note"]
                for case in cases:
                    case.status = "closed"
                    case.resolution = resolution_note
                    case.resolved_by = request.user
                    case.save()
                    updated_count += 1

            messages.success(
                request, f"Bulk action completed successfully on {updated_count} cases"
            )
            return redirect("support:case_list")
    else:
        form = BulkCaseActionForm()

    return render(
        request,
        "support/cases/case_bulk_actions.html",
        {
            "form": form,
            "cases": SupportCase.objects.filter(status__in=["open", "in_progress"])[
                :50
            ],
        },
    )


# ===== LEGACY VIEWS =====


# Placeholder views for specific legal documents
def privacy_policy_view(request):
    return LegalDocumentDetailView.as_view()(request, document_type="privacy_policy")


def terms_of_service_view(request):
    return LegalDocumentDetailView.as_view()(request, document_type="terms_of_service")


def data_protection_view(request):
    return LegalDocumentDetailView.as_view()(request, document_type="data_protection")


def cookie_policy_view(request):
    return LegalDocumentDetailView.as_view()(request, document_type="cookie_policy")


def accessibility_statement_view(request):
    return LegalDocumentDetailView.as_view()(
        request, document_type="accessibility_statement"
    )


# Main support dashboard/landing page
def support_home(request):
    articles = HelpCenterArticle.objects.filter(is_published=True).order_by(
        "-created_at"
    )[:5]
    faqs = FAQ.objects.filter(is_published=True).order_by("order")[:5]
    resources = Resource.objects.filter(is_published=True).order_by("-created_at")[:5]
    return render(
        request,
        "support/support_home.html",
        {
            "articles": articles,
            "faqs": faqs,
            "resources": resources,
        },
    )


# Support Staff Dashboard
def support_staff_dashboard(request):
    if (
        not request.user.is_authenticated
        or not request.user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists()
    ):
        return HttpResponseForbidden("Access denied. Support staff only.")

    # Get dashboard statistics
    total_tickets = ContactSubmission.objects.count()
    unresolved_tickets = ContactSubmission.objects.filter(is_resolved=False).count()
    resolved_today = ContactSubmission.objects.filter(
        is_resolved=True, resolved_at__date=timezone.now().date()
    ).count()

    # Case statistics
    total_cases = SupportCase.objects.count()
    open_cases = SupportCase.objects.filter(status="open").count()
    overdue_cases = SupportCase.objects.filter(
        Q(estimated_resolution_time__isnull=False)
        & Q(created_at__lt=timezone.now() - timezone.timedelta(hours=1))
    ).count()

    recent_tickets = ContactSubmission.objects.order_by("-created_at")[:10]
    recent_cases = SupportCase.objects.order_by("-created_at")[:10]
    recent_articles = HelpCenterArticle.objects.order_by("-updated_at")[:5]

    context = {
        "total_tickets": total_tickets,
        "unresolved_tickets": unresolved_tickets,
        "resolved_today": resolved_today,
        "total_cases": total_cases,
        "open_cases": open_cases,
        "overdue_cases": overdue_cases,
        "recent_tickets": recent_tickets,
        "recent_cases": recent_cases,
        "recent_articles": recent_articles,
    }

    return render(request, "support/dashboard/dashboard.html", context)


# ===== MONITORING VIEWS =====


def system_kpi_monitoring(request):
    if (
        not request.user.is_authenticated
        or not request.user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists()
    ):
        return HttpResponseForbidden("Access denied. Support staff only.")

    from apps.analytics.models import KPI, KPIMeasurement

    # Get recent KPI measurements
    recent_measurements = KPIMeasurement.objects.select_related("kpi").order_by(
        "-measured_at"
    )[:50]

    # Get KPI categories for filtering
    kpi_categories = KPI.KPICategory.choices

    context = {
        "recent_measurements": recent_measurements,
        "kpi_categories": kpi_categories,
    }

    return render(request, "support/monitoring/kpi.html", context)


def audit_log_monitoring(request):
    if (
        not request.user.is_authenticated
        or not request.user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists()
    ):
        return HttpResponseForbidden("Access denied. Support staff only.")

    from apps.audit.models import AuditLog

    # Get recent audit logs
    audit_logs = AuditLog.objects.select_related("user").order_by("-timestamp")[:100]

    # Get unique actions for filtering
    actions = AuditLog.objects.values_list("action", flat=True).distinct()

    context = {
        "audit_logs": audit_logs,
        "actions": actions,
    }

    return render(request, "support/monitoring/audit.html", context)


def login_history_monitoring(request):
    if (
        not request.user.is_authenticated
        or not request.user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists()
    ):
        return HttpResponseForbidden("Access denied. Support staff only.")

    from apps.users.models import LoginHistory

    # Get recent login history
    login_history = LoginHistory.objects.select_related("user").order_by("-login_time")[
        :100
    ]

    # Check for suspicious activities (failed logins, unusual times, etc.)
    suspicious_logins = LoginHistory.objects.filter(success=False).order_by(
        "-login_time"
    )[:20]

    context = {
        "login_history": login_history,
        "suspicious_logins": suspicious_logins,
    }

    return render(request, "support/security/login_history.html", context)


def user_session_monitoring(request):
    if (
        not request.user.is_authenticated
        or not request.user.user_roles.filter(
            role__role_type__in=["support", "admin", "principal", "super_admin"]
        ).exists()
    ):
        return HttpResponseForbidden("Access denied. Support staff only.")

    from apps.users.models import UserSession

    # Get active sessions
    active_sessions = (
        UserSession.objects.filter(is_active=True)
        .select_related("user")
        .order_by("-last_activity")[:50]
    )

    # Get sessions that haven't been active for a while (potentially abandoned)
    stale_sessions = (
        UserSession.objects.filter(
            is_active=True,
            last_activity__lt=timezone.now() - timezone.timedelta(hours=24),
        )
        .select_related("user")
        .order_by("-last_activity")[:20]
    )

    context = {
        "active_sessions": active_sessions,
        "stale_sessions": stale_sessions,
    }

    return render(request, "support/security/user_sessions.html", context)
