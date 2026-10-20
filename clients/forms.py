"""Client forms (PRD RF-002)."""

from django import forms

from clients.models import Client


class ClientForm(forms.ModelForm):
    """Business fields only: ``is_active`` is toggled by dedicated actions."""

    class Meta:
        model = Client
        fields = ('name', 'phone', 'email', 'notes')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nome do cliente'}),
            'phone': forms.TextInput(attrs={'placeholder': '(11) 99999-9999'}),
            'email': forms.EmailInput(attrs={'placeholder': 'cliente@example.com'}),
            'notes': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Observações gerais sobre o cliente'}
            ),
        }
