"""Vistas del módulo `tasks`"""

import os
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from tasks.tasks import check_pokemon_prices, actualizar_pokedex_automatica


@csrf_exempt
@require_GET
def trigger_check_prices(request):
    token = request.GET.get("token")
    expected_token = os.getenv("CRON_SECRET_TOKEN")

    if not expected_token or token != expected_token:
        return JsonResponse({"error": "No autorizado"}, status=403)

    resultado = check_pokemon_prices()
    return JsonResponse({"status": "ok", "resultado": resultado})


@csrf_exempt
@require_GET
def trigger_update_pokedex(request):
    token = request.GET.get("token")
    expected_token = os.getenv("CRON_SECRET_TOKEN")

    if not expected_token or token != expected_token:
        return JsonResponse({"error": "No autorizado"}, status=403)

    resultado = actualizar_pokedex_automatica()
    return JsonResponse({"status": "ok", "resultado": resultado})
