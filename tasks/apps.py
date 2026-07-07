"""Configuración de la aplicación de tareas periódicas."""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    """Configuración de la aplicación `tasks`.

    Define metadatos de la app y se deja preparada para futuros hooks `ready`."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"
