"""URLs de la aplicación `users`.

Define las rutas relacionadas con el perfil de usuario y sus vistas."""

from django.urls import path
from .views import profile

urlpatterns = [
    path("", profile, name="profile"),
]
