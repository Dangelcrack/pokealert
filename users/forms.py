from django import forms
from django.contrib.auth.models import User

class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Nombre",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent transition-all'
        })
    )
    last_name = forms.CharField(
        label="Apellidos",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent transition-all'
        })
    )
    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent transition-all'
        })
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]