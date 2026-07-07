"""Configuración de la aplicación de alertas."""

from django.apps import AppConfig


class AlertsConfig(AppConfig):
    """AppConfig para la aplicación `alerts`.

    Define metadatos de la app y sirve como punto para hooks de inicialización."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "alerts"
