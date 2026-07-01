import logging
import requests
from typing import Any, Dict, List, Optional
from django.conf import settings  # 🌟 Corregido: Import oficial y seguro de Django

logger = logging.getLogger(__name__)

API_URL = "https://api.pokemontcg.io/v2/cards"


def _get_headers() -> dict:
    """
    Obtiene la API Key validada desde los settings de Django.
    """
    api_key = getattr(settings, "POKEMON_TCG_API_KEY", "").strip()

    headers = {}
    if api_key:
        headers["X-Api-Key"] = api_key
    else:
        logger.warning(
            "⚠️ Alerta: Ejecutando peticiones a Pokémon TCG sin API Key válida."
        )

    return headers


def _get(
    url: str, params: Optional[dict] = None, timeout: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Wrapper único para todas las llamadas HTTP.
    Centraliza headers, timeouts cortos y captura errores para evitar colgar el servidor.
    """
    try:
        response = requests.get(
            url,
            headers=_get_headers(),
            params=params,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.HTTPError:
        return None
    except requests.exceptions.RequestException:
        return None


def fetch_cards(query: str, page: int = 1, page_size: int = 20) -> List[dict]:
    """
    Devuelve lista de cartas filtradas por query.
    Optimizado con un page_size menor por defecto para evitar Timeouts.
    """
    data = _get(
        API_URL,
        params={
            "q": query,
            "page": page,
            "pageSize": page_size,
        },
        timeout=8,  # Margen ligeramente mayor por ser paginación o búsqueda normal
    )

    if not data:
        return []
    return data.get("data", [])


def fetch_card(card_id: str) -> Dict[str, Any]:
    """
    Devuelve una carta concreta por ID.
    """
    data = _get(
        f"{API_URL}/{card_id}",
        timeout=5,
    )

    if not data:
        return {}
    return data.get("data", {})


def search_cards(query: str, page_size: int = 10) -> List[dict]:
    """
    Búsqueda súper ligera para componentes en tiempo real (ej: autocomplete o previews).
    """
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
