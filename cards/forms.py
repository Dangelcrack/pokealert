"""Formularios de Django para gestión de usuarios en el módulo de cartas."""

from django import forms
from django.contrib.auth.models import User


class UserUpdateForm(forms.ModelForm):
    """Formulario para actualizar datos básicos del usuario.

    Campos expuestos: `first_name`, `last_name`, `email`.
    Se usa en la vista de perfil para editar información pública del usuario."""

    class Meta:
        """Meta para `UserUpdateForm` que define el modelo y los campos incluidos."""

        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
        ]
