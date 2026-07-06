from django import forms
from django.contrib.auth.models import User

AVATAR_CHOICES = [
    ('pikachu', 'Pikachu'),
    ('charizard', 'Charizard'),
    ('gengar', 'Gengar'),
    ('mewtwo', 'Mewtwo'),
    ('lugia', 'Lugia'),
]

class UserUpdateForm(forms.ModelForm):
    username = forms.CharField(label="Nombre de Usuario / Alias", required=True)
    first_name = forms.CharField(label="Nombre", required=False)
    last_name = forms.CharField(label="Apellidos", required=False)
    email = forms.EmailField(label="Correo electrónico", required=True)
    pokemon_avatar = forms.ChoiceField(
        label="Tu Pokémon Acompañante (Avatar)",
        choices=AVATAR_CHOICES,
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'pokemon_avatar']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'auth-input'