"""Scheduling forms (PRD RF-004)."""

from django import forms

from scheduling.models import WalkSchedule


class ScheduleForm(forms.ModelForm):
    """Business fields only: ``is_active`` is toggled by dedicated actions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Design system checkbox pattern (custom-control-input).
        for field in WalkSchedule.WEEKDAY_FIELDS:
            self.fields[field].widget.attrs['class'] = 'custom-control-input'

    class Meta:
        model = WalkSchedule
        fields = (
            'frequency',
            'monday',
            'tuesday',
            'wednesday',
            'thursday',
            'friday',
            'saturday',
            'sunday',
            'start_date',
            'end_date',
        )
        widgets = {
            'frequency': forms.Select(),
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Model.clean() (weekdays, period order, overlaps) runs via
        # full_clean in the ModelForm — this keeps admin consistent too.
        return cleaned_data
