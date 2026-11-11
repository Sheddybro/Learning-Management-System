# apps/finance/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal

from .models import FeeStructure, FeeDiscount, Invoice, InvoiceItem, Payment, Expense, FinancialReport
from apps.academics.models import AcademicSession, Class, Student
from apps.users.models import User


class InstitutionScopedModelForm(forms.ModelForm):
    """Model form whose related-object choices are limited to one school."""

    def __init__(self, *args, institution=None, **kwargs):
        self.institution = institution
        super().__init__(*args, **kwargs)

    def scope(self, queryset):
        if self.institution is None:
            return queryset.none()
        return queryset.filter(institution=self.institution)

    def staff_users(self):
        if self.institution is None:
            return User.objects.none()
        return User.objects.filter(
            is_staff=True,
            is_active=True,
            user_roles__institution=self.institution,
            user_roles__status="active",
        ).distinct()


class FeeStructureForm(InstitutionScopedModelForm):
    """
    Form for creating and updating fee structures.
    """
    class Meta:
        model = FeeStructure
        fields = [
            'name', 'code', 'fee_type', 'academic_session', 'applicable_class',
            'amount', 'billing_cycle', 'due_day', 'is_optional', 'description',
            'tax_rate', 'late_fee_per_day', 'max_late_fee', 'discount_eligible', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g., Annual Tuition Fee')}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g., TUITION-2024')}),
            'fee_type': forms.Select(attrs={'class': 'form-control'}),
            'academic_session': forms.Select(attrs={'class': 'form-control'}),
            'applicable_class': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00}),
            'billing_cycle': forms.Select(attrs={'class': 'form-control'}),
            'due_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00, 'max': 100.00}),
            'late_fee_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00}),
            'max_late_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00}),
            'discount_eligible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'applicable_class': _('Leave blank if this fee applies to all classes in the academic session.'),
            'due_day': _('Day of the month the fee is due (1-31).'),
            'tax_rate': _('Tax rate in percentage (e.g., 5.00 for 5%).'),
            'late_fee_per_day': _('Amount charged per day for late payments.'),
            'max_late_fee': _('Maximum late fee that can be charged for this fee structure.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['academic_session'].queryset = self.scope(
            AcademicSession.objects.filter(status="active")
        )
        self.fields['applicable_class'].queryset = self.scope(
            Class.objects.filter(status="active")
        )

        self.fields['academic_session'].empty_label = _("Select Academic Session")
        self.fields['applicable_class'].empty_label = _("Select Applicable Class (Optional)")

    def clean(self):
        cleaned_data = super().clean()
        academic_session = cleaned_data.get('academic_session')
        fee_type = cleaned_data.get('fee_type')
        applicable_class = cleaned_data.get('applicable_class')
        code = cleaned_data.get('code')

        # Unique constraint check
        if academic_session and fee_type:
            if applicable_class and applicable_class.institution_id != academic_session.institution_id:
                self.add_error("applicable_class", _("Choose a class from the selected school's institution."))
            duplicate_fee = FeeStructure.objects.filter(
                institution=self.institution,
                academic_session=academic_session,
                fee_type=fee_type,
                applicable_class=applicable_class
            ).exclude(pk=self.instance.pk).exists()
            if duplicate_fee:
                raise forms.ValidationError(_('A fee structure with this type already exists for this academic session and class.'))
        
        if code:
            if FeeStructure.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(_('A fee structure with this code already exists.'))

        return cleaned_data


class FeeDiscountForm(InstitutionScopedModelForm):
    """
    Form for creating and updating fee discounts.
    """
    class Meta:
        model = FeeDiscount
        fields = [
            'name', 'code', 'discount_type', 'category', 'value',
            'max_discount_amount', 'applicable_fee_types', 'start_date',
            'end_date', 'is_active', 'description', 'requirements', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g., Early Bird Discount')}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g., EARLYBIRD20')}),
            'discount_type': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00}),
            'max_discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00}),
            'applicable_fee_types': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('JSON format for complex requirements')}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'value': _('Percentage (e.g., 10 for 10%) or fixed amount.'),
            'max_discount_amount': _('Maximum amount that can be discounted (for percentage discounts).'),
            'applicable_fee_types': _('Select specific fee types this discount applies to. Leave blank for all.'),
            'requirements': _('Optional: JSON object for advanced discount conditions (e.g., {"min_grade": "G5"}).'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['applicable_fee_types'].queryset = self.scope(
            FeeStructure.objects.filter(status="active")
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        value = cleaned_data.get('value')
        discount_type = cleaned_data.get('discount_type')
        code = cleaned_data.get('code')

        if start_date and end_date and start_date >= end_date:
            self.add_error('end_date', _('End date must be after start date.'))
        
        if value is not None and value < Decimal('0.00'):
            self.add_error('value', _('Discount value cannot be negative.'))
        
        if discount_type == FeeDiscount.DiscountType.PERCENTAGE and value is not None and value > Decimal('100.00'):
            self.add_error('value', _('Percentage discount cannot exceed 100%.'))
        
        if code:
            if FeeDiscount.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(_('A discount with this code already exists.'))

        return cleaned_data


class InvoiceForm(InstitutionScopedModelForm):
    """
    Form for creating and updating invoices.
    """
    class Meta:
        model = Invoice
        fields = [
            'student', 'academic_session', 'billing_period', 'issue_date',
            'due_date', 'status', 'notes', 'terms_and_conditions'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'academic_session': forms.Select(attrs={'class': 'form-control'}),
            'billing_period': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g., Q1 2024, January 2024')}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'terms_and_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'status': _('Automatically updated based on payments, but can be manually set.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = self.scope(
            Student.objects.filter(status="active", user__is_active=True)
        )
        self.fields['academic_session'].queryset = self.scope(
            AcademicSession.objects.filter(status="active")
        )

        self.fields['student'].empty_label = _("Select Student")
        self.fields['academic_session'].empty_label = _("Select Academic Session")

    def clean(self):
        cleaned_data = super().clean()
        issue_date = cleaned_data.get('issue_date')
        due_date = cleaned_data.get('due_date')
        student = cleaned_data.get("student")
        academic_session = cleaned_data.get("academic_session")

        if issue_date and due_date and issue_date > due_date:
            self.add_error('due_date', _('Due date cannot be before issue date.'))
        if student and academic_session and student.institution_id != academic_session.institution_id:
            self.add_error("student", _("Select a student from the selected school's institution."))
        
        return cleaned_data


class InvoiceItemForm(InstitutionScopedModelForm):
    """
    Form for adding/editing individual invoice items.
    """
    class Meta:
        model = InvoiceItem
        fields = ['invoice', 'fee_structure', 'quantity', 'unit_price', 'tax_rate', 'discount_amount', 'description', 'status']
        widgets = {
            'invoice': forms.Select(attrs={'class': 'form-control'}),
            'fee_structure': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00, 'max': 100.00}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.00}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice'].queryset = Invoice.objects.filter(
            status__in=["draft", "issued", "partial"],
            student__institution=self.institution,
        ) if self.institution else Invoice.objects.none()
        self.fields['fee_structure'].queryset = self.scope(
            FeeStructure.objects.filter(status="active")
        )

        self.fields['invoice'].empty_label = _("Select Invoice")
        self.fields['fee_structure'].empty_label = _("Select Fee Type")

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')
        tax_rate = cleaned_data.get('tax_rate')
        discount_amount = cleaned_data.get('discount_amount')
        invoice = cleaned_data.get("invoice")
        fee_structure = cleaned_data.get("fee_structure")

        if invoice and fee_structure and invoice.institution_id != fee_structure.institution_id:
            self.add_error("fee_structure", _("Choose a fee structure from the invoice's school."))

        if quantity is not None and quantity < 1:
            self.add_error('quantity', _('Quantity must be at least 1.'))
        if unit_price is not None and unit_price < Decimal('0.00'):
            self.add_error('unit_price', _('Unit price cannot be negative.'))
        if tax_rate is not None and (tax_rate < Decimal('0.00') or tax_rate > Decimal('100.00')):
            self.add_error('tax_rate', _('Tax rate must be between 0 and 100.'))
        if discount_amount is not None and discount_amount < Decimal('0.00'):
            self.add_error('discount_amount', _('Discount amount cannot be negative.'))
        
        return cleaned_data


class PaymentForm(InstitutionScopedModelForm):
    """
    Form for recording payments.
    """
    class Meta:
        model = Payment
        fields = [
            'invoice', 'student', 'amount', 'payment_method', 'payment_date',
            'received_by', 'status', 'reference_number', 'bank_name',
            'cheque_number', 'transaction_id', 'notes', 'receipt_issued'
        ]
        widgets = {
            'invoice': forms.Select(attrs={'class': 'form-control'}),
            'student': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.01}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'received_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'cheque_number': forms.TextInput(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'receipt_issued': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'invoice': _('Select the invoice this payment is for.'),
            'student': _('Select the student making this payment.'),
            'received_by': _('Staff member who received the payment.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice'].queryset = Invoice.objects.filter(
            status__in=["issued", "partial"],
            student__institution=self.institution,
        ) if self.institution else Invoice.objects.none()
        self.fields['student'].queryset = self.scope(
            Student.objects.filter(status="active", user__is_active=True)
        )
        self.fields['received_by'].queryset = self.staff_users()

        self.fields['invoice'].empty_label = _("Select Invoice")
        self.fields['student'].empty_label = _("Select Student")
        self.fields['received_by'].empty_label = _("Select Receiver")

    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get('invoice')
        student = cleaned_data.get("student")
        amount = cleaned_data.get('amount')

        if invoice and student and invoice.student_id != student.pk:
            self.add_error("student", _("The selected student does not match the invoice."))
        if invoice and amount:
            if amount > invoice.balance_due:
                self.add_error('amount', _(f'Payment amount cannot exceed the remaining balance of {invoice.balance_due}.'))
        
        return cleaned_data


class ExpenseForm(InstitutionScopedModelForm):
    """
    Form for creating and updating school expenses.
    """
    class Meta:
        model = Expense
        fields = [
            'category', 'description', 'amount', 'expense_date', 'vendor',
            'invoice_number', 'approved_by', 'paid_by', 'payment_method',
            'receipt_attachment', 'notes', 'status'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Brief description of the expense')}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.01}),
            'expense_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'vendor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Vendor name (optional)')}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Vendor invoice number (optional)')}),
            'approved_by': forms.Select(attrs={'class': 'form-control'}),
            'paid_by': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'receipt_attachment': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'approved_by': _('Staff member who approved this expense.'),
            'paid_by': _('Staff member who made the payment (if different from approver).'),
            'receipt_attachment': _('Link to an uploaded receipt or document.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['approved_by'].queryset = self.staff_users()
        self.fields['paid_by'].queryset = self.staff_users()
        from apps.academics.models import FileAttachment
        self.fields['receipt_attachment'].queryset = self.scope(
            FileAttachment.objects.filter(status="active")
        )

        self.fields['approved_by'].empty_label = _("Select Approver")
        self.fields['paid_by'].empty_label = _("Select Payer (Optional)")
        self.fields['receipt_attachment'].empty_label = _("Select Receipt (Optional)")

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')

        if amount is not None and amount < Decimal('0.01'):
            self.add_error('amount', _('Expense amount must be at least 0.01.'))
        
        return cleaned_data


class FinancialReportForm(InstitutionScopedModelForm):
    """
    Form for generating and managing financial reports.
    """
    class Meta:
        model = FinancialReport
        fields = [
            'report_type', 'title', 'academic_session', 'start_date',
            'end_date', 'report_data', 'summary', 'is_published', 'status'
        ]
        widgets = {
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g., Q1 2024 Income Statement')}),
            'academic_session': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'report_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': _('JSON data for the report content')}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'report_data': _('Raw JSON data representing the report content.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['academic_session'].queryset = self.scope(
            AcademicSession.objects.filter(status="active")
        )

        self.fields['academic_session'].empty_label = _("Select Academic Session")

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', _('End date must be after start date.'))
        
        return cleaned_data
