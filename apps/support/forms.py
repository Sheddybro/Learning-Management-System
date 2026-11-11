from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    ContactSubmission,
    HelpCenterArticle,
    Resource,
    FAQ,
    Category,
    Tag,
    SupportCase,
    CaseUpdate,
    CaseParticipant,
    CaseAttachment,
)
from apps.users.models import User
from apps.academics.models import Student


class ContactForm(forms.ModelForm):
    """
    Form for contact submissions.
    """

    class Meta:
        model = ContactSubmission
        fields = ["name", "email", "phone", "subject", "message", "priority"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Your Name")}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": _("Your Email")}
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Phone Number (Optional)"),
                }
            ),
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Subject (Optional)")}
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": _("Your Message"),
                }
            ),
            "priority": forms.Select(attrs={"class": "form-control"}),
        }


class HelpCenterArticleForm(forms.ModelForm):
    """
    Form for creating and editing help center articles.
    """

    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = HelpCenterArticle
        fields = [
            "title",
            "content",
            "category",
            "tags",
            "article_category",
            "is_published",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Article Title")}
            ),
            "content": forms.Textarea(
                attrs={"class": "form-control", "rows": 15, "id": "article-content"}
            ),
            "category": forms.Select(attrs={"class": "form-control"}),
            "article_category": forms.Select(attrs={"class": "form-control"}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ResourceForm(forms.ModelForm):
    """
    Form for creating and editing support resources.
    """

    class Meta:
        model = Resource
        fields = [
            "title",
            "description",
            "resource_type",
            "file",
            "external_url",
            "category",
            "tags",
            "is_published",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Resource Title")}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Brief description"),
                }
            ),
            "resource_type": forms.Select(attrs={"class": "form-control"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
            "external_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://nordalms.pythonanywhere.com",
                }
            ),
            "category": forms.Select(attrs={"class": "form-control"}),
            "tags": forms.SelectMultiple(
                attrs={
                    "class": "form-control select2-multiple",
                    "data-placeholder": _("Select tags"),
                }
            ),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].queryset = Tag.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        resource_type = cleaned_data.get("resource_type")
        file = cleaned_data.get("file")
        external_url = cleaned_data.get("external_url")

        if resource_type in ["user_guide", "document"] and not file:
            raise forms.ValidationError(
                _("File is required for user guides and documents.")
            )
        elif resource_type == "link" and not external_url:
            raise forms.ValidationError(
                _("External URL is required for external links.")
            )

        return cleaned_data


class FAQForm(forms.ModelForm):
    """
    Form for creating and editing FAQs.
    """

    class Meta:
        model = FAQ
        fields = ["question", "answer", "category", "tags", "order", "is_published"]
        widgets = {
            "question": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("FAQ Question")}
            ),
            "answer": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "id": "faq-answer"}
            ),
            "category": forms.Select(attrs={"class": "form-control"}),
            "tags": forms.SelectMultiple(
                attrs={
                    "class": "form-control select2-multiple",
                    "data-placeholder": _("Select tags"),
                }
            ),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].queryset = Tag.objects.filter(is_active=True)


# ===== STUDENT SUPPORT TEAM COLLABORATION FORMS =====


class SupportCaseForm(forms.ModelForm):
    """
    Form for creating and editing support cases.
    """

    # Custom fields for better UX
    assign_participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-control select2-multiple",
                "data-placeholder": _("Select team members to assign"),
            }
        ),
        label=_("Assign Team Members"),
    )

    notify_parent = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label=_("Notify Parent/Guardian"),
        help_text=_("Send notification to student's parent/guardian"),
    )

    class Meta:
        model = SupportCase
        fields = [
            "title",
            "description",
            "case_type",
            "priority",
            "category",
            "tags",
            "estimated_resolution_time",
            "requires_parent_notification",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Brief case title")}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": _("Detailed description of the support case"),
                }
            ),
            "case_type": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "tags": forms.SelectMultiple(
                attrs={
                    "class": "form-control select2-multiple",
                    "data-placeholder": _("Select relevant tags"),
                }
            ),
            "estimated_resolution_time": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "placeholder": _("Hours")}
            ),
            "requires_parent_notification": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Filter users based on permissions (support staff, teachers, counselors, etc.)
        if self.request and hasattr(self.request, "user"):
            user = self.request.user
            # Allow assignment to support staff, teachers, counselors, admins
            self.fields["assign_participants"].queryset = (
                User.objects.filter(is_active=True)
                .filter(
                    # Support staff
                    user_roles__role__role_type__in=[
                        "support",
                        "teacher",
                        "counselor",
                        "admin",
                        "principal",
                        "school_admin",
                        "super_admin",
                    ]
                )
                .distinct()
            )

        self.fields["tags"].queryset = Tag.objects.filter(is_active=True)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.request and hasattr(self.request, "user"):
            instance.reported_by = self.request.user

        if commit:
            instance.save()
            self.save_m2m()

            # Assign participants
            assign_participants = self.cleaned_data.get("assign_participants")
            if assign_participants:
                for participant in assign_participants:
                    instance.add_participant(participant, role="member")

            # Handle parent notification
            if (
                self.cleaned_data.get("notify_parent")
                and instance.requires_parent_notification
            ):
                # Mark as notified (actual notification logic would be in view/signal)
                instance.parent_notified = True
                instance.parent_notification_date = timezone.now()
                instance.save()

        return instance


class CaseUpdateForm(forms.ModelForm):
    """
    Form for adding updates to support cases.
    """

    class Meta:
        model = CaseUpdate
        fields = ["update_type", "content", "is_private", "attachment"]
        widgets = {
            "update_type": forms.Select(attrs={"class": "form-control"}),
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": _("Add your update or comment"),
                }
            ),
            "is_private": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.case = kwargs.pop("case", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.case:
            instance.case = self.case
        if self.user:
            instance.user = self.user

        if commit:
            instance.save()

        return instance


class CaseParticipantForm(forms.ModelForm):
    """
    Form for managing case participants.
    """

    class Meta:
        model = CaseParticipant
        fields = ["user", "role"]
        widgets = {
            "user": forms.Select(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.case = kwargs.pop("case", None)
        super().__init__(*args, **kwargs)

        if self.case:
            # Exclude already assigned users
            assigned_users = self.case.participants.values_list("user", flat=True)
            self.fields["user"].queryset = User.objects.filter(is_active=True).exclude(
                id__in=assigned_users
            )

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.case:
            instance.case = self.case

        if commit:
            instance.save()

        return instance


class CaseAttachmentForm(forms.ModelForm):
    """
    Form for uploading case attachments.
    """

    class Meta:
        model = CaseAttachment
        fields = ["file", "description", "is_private"]
        widgets = {
            "file": forms.FileInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": _("Optional description"),
                }
            ),
            "is_private": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.case = kwargs.pop("case", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.case:
            instance.case = self.case
        if self.user:
            instance.uploaded_by = self.user

        if commit:
            instance.save()

        return instance


class CaseSearchForm(forms.Form):
    """
    Form for searching and filtering support cases.
    """

    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search cases...")}
        ),
        label=_("Search"),
    )

    case_type = forms.ChoiceField(
        choices=[("", _("All Types"))] + list(SupportCase.CaseType.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Case Type"),
    )

    priority = forms.ChoiceField(
        choices=[("", _("All Priorities"))] + list(SupportCase.CasePriority.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Priority"),
    )

    status = forms.ChoiceField(
        choices=[("", _("All Statuses"))] + list(SupportCase.CaseStatus.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Status"),
    )

    assigned_to_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label=_("Assigned to me"),
    )

    overdue_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label=_("Overdue cases only"),
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("From Date"),
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("To Date"),
    )


class BulkCaseActionForm(forms.Form):
    """
    Form for bulk actions on support cases.
    """

    ACTION_CHOICES = [
        ("status_change", _("Change Status")),
        ("assign_participants", _("Assign Participants")),
        ("add_tags", _("Add Tags")),
        ("set_priority", _("Set Priority")),
        ("close_cases", _("Close Cases")),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Action"),
    )

    new_status = forms.ChoiceField(
        choices=SupportCase.CaseStatus.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("New Status"),
    )

    assign_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-control select2-multiple",
                "data-placeholder": _("Select users to assign"),
            }
        ),
        label=_("Assign to Users"),
    )

    add_tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-control select2-multiple",
                "data-placeholder": _("Select tags to add"),
            }
        ),
        label=_("Add Tags"),
    )

    new_priority = forms.ChoiceField(
        choices=SupportCase.CasePriority.choices,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("New Priority"),
    )

    resolution_note = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": _("Resolution note for closed cases"),
            }
        ),
        label=_("Resolution Note"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users to support staff
        self.fields["assign_users"].queryset = User.objects.filter(
            is_active=True,
            user_roles__role__role_type__in=[
                "support",
                "teacher",
                "counselor",
                "admin",
                "principal",
                "super_admin",
            ],
        ).distinct()


class CaseEscalationForm(forms.Form):
    """
    Form for escalating support cases.
    """

    escalate_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Escalate To"),
        help_text=_("Select a senior staff member to escalate this case to"),
    )

    escalation_reason = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Explain why this case needs escalation"),
            }
        ),
        label=_("Escalation Reason"),
    )

    urgency_level = forms.ChoiceField(
        choices=[
            ("normal", _("Normal")),
            ("urgent", _("Urgent")),
            ("critical", _("Critical")),
        ],
        initial="normal",
        widget=forms.Select(attrs={"class": "form-control"}),
        label=_("Urgency Level"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to senior staff/administrators
        self.fields["escalate_to"].queryset = User.objects.filter(
            is_active=True,
            user_roles__role__role_type__in=[
                "admin",
                "principal",
                "school_admin",
                "super_admin",
            ],
        ).distinct()
