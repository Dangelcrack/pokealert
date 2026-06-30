from asyncio.log import logger

from django.apps import AppConfig


class CardsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cards'
    
def ready(self):
        # Solo se ejecutará cuando Django esté listo
        from .views import warm_up_database
        try:
            warm_up_database()
        except Exception:
            logger.warning("error procesando cards")