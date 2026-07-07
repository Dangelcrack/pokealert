"""Formularios de usuario para actualización de perfil y selección de avatar."""

from django import forms
from django.contrib.auth.models import User

AVATAR_CHOICES = [
    ("pikachu", "Pikachu"),
    ("charizard", "Charizard"),
    ("gengar", "Gengar"),
    ("mewtwo", "Mewtwo"),
    ("lugia", "Lugia"),
]


class UserUpdateForm(forms.ModelForm):
    """Formulario para actualizar perfil de usuario y seleccionar avatar.

    Campos personalizados: `pokemon_avatar` y validaciones mínimas. Asigna
    clases CSS a los widgets en `__init__`."""

    username = forms.CharField(label="Nombre de Usuario / Alias", required=True)
    first_name = forms.CharField(label="Nombre", required=False)
    last_name = forms.CharField(label="Apellidos", required=False)
    email = forms.EmailField(label="Correo electrónico", required=True)
    pokemon_avatar = forms.ChoiceField(
        label="Tu Pokémon Acompañante (Avatar)", choices=AVATAR_CHOICES, required=False
    )

    class Meta:
        """Meta para `UserUpdateForm`: define el modelo y campos incluidos."""

        model = User
        fields = ["username", "first_name", "last_name", "email", "pokemon_avatar"]

    def __init__(self, *args, **kwargs):
        """Inicializa el formulario y añade clases CSS a cada widget."""
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "auth-input"
