"""Dog forms (PRD RF-003)."""

from django import forms

from dogs.models import Dog


class DogForm(forms.ModelForm):
    """Business fields only: ``is_active`` is toggled by dedicated actions."""

    class Meta:
        model = Dog
        fields = ('name', 'breed', 'notes')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nome do cachorro'}),
            'breed': forms.TextInput(attrs={'placeholder': 'Raça do cachorro'}),
            'notes': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Observações gerais sobre o cachorro'}
            ),
        }
