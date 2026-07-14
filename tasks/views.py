"""Vistas para ejecutar tareas periódicas mediante endpoints HTTP.

Modificado para ejecutar tareas pesadas en segundo plano y evitar HTTP
Timeouts.
"""

import logging
import os
import threading

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from tasks.tasks import (
    actualizar_pokedex_automatica,
    check_pokemon_prices,
)

logger = logging.getLogger(__name__)


def _authorized(request):
    token = request.GET.get("token")
    expected = os.getenv("CRON_SECRET_TOKEN")

    return expected and token == expected


@csrf_exempt
@require_GET
def trigger_check_prices(request):
    """Lanza la actualización de precios en segundo plano."""
    if not _authorized(request):
        return JsonResponse({"error": "No autorizado"}, status=403)

    try:
        # Iniciamos la función pesada en un hilo independiente
        thread = threading.Thread(target=check_pokemon_prices)
        thread.start()

        # Respondemos de inmediato para evitar que cron-job.org aborte por Timeout
        return JsonResponse(
            {
                # Usamos 'started' para dejar claro que no ha terminado, sino que ha comenzado
                "status": "started",
                "message": "Tarea de actualización de precios iniciada en segundo plano.",
            }
        )

    except Exception:
        logger.exception("Error al intentar lanzar check_pokemon_prices")

        return JsonResponse(
            {
                "status": "error",
                "message": "Error interno al iniciar la tarea",
            },
            status=500,
        )


@csrf_exempt
@require_GET
def trigger_update_pokedex(request):
    """Lanza la sincronización de especies en segundo plano."""
    if not _authorized(request):
        return JsonResponse({"error": "No autorizado"}, status=403)

    try:
        # Iniciamos la sincronización de la PokéAPI en segundo plano
        thread = threading.Thread(target=actualizar_pokedex_automatica)
        thread.start()

        return JsonResponse(
            {
                "status": "started",
                "message": "Tarea de sincronización de Pokédex iniciada en segundo plano.",
            }
        )

    except Exception:
        logger.exception("Error al intentar lanzar actualizar_pokedex_automatica")

        return JsonResponse(
            {
                "status": "error",
                "message": "Error interno al iniciar la tarea",
            },
            status=500,
        )
