"""Configuración de la aplicación cards and warm-up initialization."""

from asyncio.log import logger

from django.apps import AppConfig


class CardsConfig(AppConfig):
    """Configuración de la aplicación `cards`.

    Establece la configuración predeterminada de la app y ejecuta un calentamiento
    inicial de la base de datos para reducir latencia en la primera petición."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cards"

    def ready(self):
        """Callback que se ejecuta cuando Django carga la aplicación.

        Importa y ejecuta `warm_up_database()` para inicializar conexiones y
        mitigar demoras en requests iniciales."""
        from .views import warm_up_database

        try:
            warm_up_database()
        except Exception:
            logger.warning("error procesando cards")
