from django import forms
from django.contrib.auth.models import User

AVATAR_CHOICES = [
    ('pikachu', '⚡ Pikachu'),
    ('charizard', '🔥 Charizard'),
    ('gengar', '👻 Gengar'),
    ('mewtwo', '🔮 Mewtwo'),
    ('lugia', '🌊 Lugia'),
]

class UserUpdateForm(forms.ModelForm):
    # ✅ ARREGLADO: Declaramos username explícitamente con tus mismos estilos de Tailwind
    username = forms.CharField(
        label="Nombre de Usuario / Alias",
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'
        })
    )
    
    first_name = forms.CharField(
        label="Nombre", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'})
    )
    
    last_name = forms.CharField(
        label="Apellidos", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'})
    )
    
    email = forms.EmailField(
        label="Correo electrónico", 
        required=True, 
        widget=forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'})
    )
    
    pokemon_avatar = forms.ChoiceField(
        label="Tu Pokémon Acompañante (Avatar)",
        choices=AVATAR_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500'})
    )

    class Meta:
        model = User
        # Mantenemos tu orden de campos preferido
        fields = ['username', 'first_name', 'last_name', 'email', 'pokemon_avatar']