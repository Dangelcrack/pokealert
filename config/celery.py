"""Configuración mínima de Celery para el proyecto.

Define la aplicación Celery y carga la configuración desde `settings`.
"""

import os
from celery import Celery

# Establece el módulo de configuración de Django por defecto para celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

# Usar una cadena aquí significa que el worker no tiene que serializar
# el objeto de configuración para los procesos hijos.
# namespace='CELERY' significa que todas las claves de configuración
# relacionadas con celery deben tener el prefijo `CELERY_`.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Carga las tareas de todas las aplicaciones registradas en Django
app.autodiscover_tasks()
