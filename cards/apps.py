from django.apps import AppConfig


class CardsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cards'
    
def ready(self):
        # Solo se ejecutará cuando Django esté listo
        from .views import warm_up_database
        try:
            warm_up_database()
        except:
            pass # Ignorar si la tabla aún no existe durante el migrate