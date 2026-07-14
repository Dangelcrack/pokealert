"""Servicio de gestión de opciones de filtro (catálogo).

Sincroniza rarezas, supertypes, subtypes y artistas con la API externa,
y gestiona la caché de opciones usada por los menús de filtro del
frontend.
"""

from django.core.cache import cache

from cards.models import Rarity, Supertype, Subtype, Artist
from cards.services.text_utils import normalize
from cards.utils import get_filter_options as get_api_filter_options

CACHE_KEY = "filter_options_all"
CACHE_TTL_SECONDS = 3600


def invalidate_filter_options_cache() -> None:
    """Elimina la entrada en caché que contiene las opciones de filtro.

    Se usa después de crear nuevos registros relacionados con filtros
    para forzar recálculo en la siguiente petición.
    """
    cache.delete(CACHE_KEY)


def sync_api_filter_values() -> None:
    """Solicita valores de filtros a la API externa y los persiste en la DB
    local.

    Crea `Supertypes`, `Subtypes` y `Rarities` si no existen para
    asegurar que los menús de filtro muestren todas las opciones
    disponibles.
    """
    mapping = [
        (Supertype, "supertypes", "display_name"),
        (Subtype, "subtypes", "display_name"),
        (Rarity, "rarities", "display_name"),
    ]
    for model, filter_type, display_field in mapping:
        options = get_api_filter_options(filter_type)
        for label in options:
            if not label:
                continue
            normalized = normalize(label)
            model.objects.get_or_create(
                name=normalized,
                defaults={display_field: label},
            )


def get_filter_options(filter_name: str | None = None):
    """Devuelve las opciones de filtro (cached) para filtros de la interfaz.

    Si la caché está vacía o la base de datos no parece completa,
    sincroniza los valores con la API externa antes de construir el
    resultado. Si se pasa `filter_name`, devuelve solo ese subconjunto.
    """
    filters = cache.get(CACHE_KEY)

    db_complete = (
        Supertype.objects.count() >= 3
        and Subtype.objects.count() >= 20
        and Rarity.objects.count() >= 20
    )

    if filters is None or not db_complete:
        sync_api_filter_values()

        filters = {
            "supertypes": list(Supertype.objects.all().order_by("display_name")),
            "subtypes": list(Subtype.objects.all().order_by("display_name")),
            "rarities": list(Rarity.objects.all().order_by("display_name")),
            "artists": list(Artist.objects.all().order_by("name")),
        }
        cache.set(CACHE_KEY, filters, CACHE_TTL_SECONDS)

    if filter_name:
        return filters.get(filter_name)
    return filters
