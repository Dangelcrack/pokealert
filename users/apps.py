"""Configuración de la aplicación de usuarios."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Configuración de la aplicación `users`.

    Contiene metadatos y sirve como punto para hooks de inicialización."""

    name = "users"
