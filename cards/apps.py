"""Configuración de la aplicación cards and warm-up initialization."""

from django.apps import AppConfig


class CardsConfig(AppConfig):
    """Configuración de la aplicación `cards`.

    Establece la configuración predeterminada de la app y ejecuta un calentamiento
    inicial de la base de datos para reducir latencia en la primera petición."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cards"
