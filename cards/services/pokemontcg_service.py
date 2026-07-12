"""Módulo de integración con la API de Pokémon TCG.

Centraliza las llamadas HTTP, manejo de headers y transformación mínima de
respuesta para el resto de la aplicación."""

import logging
import requests
from typing import Any, Dict, List, Optional
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

API_URL = "https://api.pokemontcg.io/v2/cards"


def _get_headers() -> dict:
    """Obtiene la API Key validada desde los settings de Django."""
    api_key = getattr(settings, "POKEMON_TCG_API_KEY", "").strip()

    headers = {}
    if api_key:
        headers["X-Api-Key"] = api_key
    else:
        logger.warning("⚠️ Alerta: Ejecutando peticiones a Pokémon TCG sin API Key válida.")

    return headers


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type((requests.exceptions.HTTPError, requests.exceptions.Timeout)),
)
def _execute_request(
    url: str, headers: dict, params: Optional[dict], timeout: int
) -> requests.Response:
    """Dispara la petición y evalúa si se debe reintentar basado en códigos de estado."""
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    if response.status_code >= 500:
        response.raise_for_status()

    return response


def _get(url: str, params: Optional[dict] = None, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Wrapper único para todas las llamadas HTTP.
    Centraliza headers, timeouts cortos y captura errores para evitar colgar el servidor."""
    try:
        response = _execute_request(url, headers=_get_headers(), params=params, timeout=timeout)

        if response.status_code != 200:
            logger.error(
                f"Error {response.status_code} no reintentable en API Pokémon TCG para la URL: {url}"
            )
            return None

        return response.json()

    except (
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError,
        requests.exceptions.RequestException,
    ) as e:
        logger.error(f" La petición falló definitivamente tras los reintentos: {str(e)}")
        return None


def fetch_cards(query: str, page: int = 1, page_size: int = 20) -> List[dict]:
    """Devuelve lista de cartas filtradas por query.
    Optimizado con un page_size menor por defecto para evitar Timeouts."""
    data = _get(
        API_URL,
        params={
            "q": query,
            "page": page,
            "pageSize": page_size,
        },
        timeout=8,
    )

    if not data:
        return []
    return data.get("data", [])


def fetch_card(card_id: str) -> Dict[str, Any]:
    """Devuelve una carta concreta por ID."""
    data = _get(
        f"{API_URL}/{card_id}",
        timeout=5,
    )

    if not data:
        return {}
    return data.get("data", {})


def search_cards(query: str, page_size: int = 10) -> List[dict]:
    """Búsqueda súper ligera para componentes en tiempo real (ej: autocomplete o previews)."""
    data = _get(
        API_URL,
        params={
            "q": query,
            "pageSize": page_size,
        },
        timeout=4,
    )

    if not data:
        return []
    return data.get("data", [])
