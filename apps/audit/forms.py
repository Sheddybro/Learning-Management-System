class AuditLogSearchForm(forms.Form):
    """
    Form for searching and filtering AuditLog entries.
    """
    ACTION_CHOICES = [('', _('All Actions'))] + list(AuditLog.ActionType.choices)
    DATE_RANGE_CHOICES = [
        ('', _('Any Time')),
        ('today', _('Today')),
        ('week', _('This Week')),
        ('month', _('This Month')),
        ('year', _('This Year')),
        ('custom', _('Custom Range')),
    ]

    user = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        label=_('User'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        label=_('Action Type'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    model_name = forms.CharField(
        required=False,
        label=_('Model Name'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('e.g., academics.Student')
        })
    )
    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        required=False,
        label=_('Date Range'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        label=_('From Date'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        required=False,
        label=_('To Date'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    ip_address = forms.GenericIPAddressField(
        required=False,
        label=_('IP Address'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('192.168.1.1')
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.users.models import User
        self.fields['user'].queryset = User.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if date_range == 'custom':
            if not start_date or not end_date:
                raise ValidationError(
                    _('Both start date and end date are required for custom date range.')
                )
            if start_date > end_date:
                raise ValidationError(
                    _('Start date cannot be after end date.')
                )

        return cleaned_data