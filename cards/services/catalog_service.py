"""Servicio de gestión de opciones de filtro (catálogo)."""

import logging
from django.core.cache import cache
from cards.models import Rarity, Supertype, Subtype, Artist
from cards.services.text_utils import normalize
from cards.utils import get_filter_options as get_api_filter_options

logger = logging.getLogger(__name__)

CACHE_KEY = "filter_options_all"
CACHE_TTL_SECONDS = 3600


def invalidate_filter_options_cache() -> None:
    """Elimina la entrada en caché."""
    cache.delete(CACHE_KEY)


def sync_api_filter_values() -> None:
    """Solicita valores a la API y persiste localmente."""
    mapping = [
        (Supertype, "supertypes", "display_name"),
        (Subtype, "subtypes", "display_name"),
        (Rarity, "rarities", "display_name"),
    ]
    for model, filter_type, display_field in mapping:
        try:
            options = get_api_filter_options(filter_type)
            if not options:
                continue
            for label in options:
                if not label:
                    continue
                normalized = normalize(label)
                model.objects.get_or_create(
                    name=normalized,
                    defaults={display_field: label},
                )
        except Exception as e:
            logger.error(f"Error sincronizando {filter_type}: {e}")


def get_filter_options(filter_name: str | None = None):
    """Devuelve opciones de filtro, asegurando sincronización inicial."""
    filters = cache.get(CACHE_KEY)

    if filters is None:
        # Verificamos si tenemos datos base en DB
        db_has_data = Supertype.objects.exists() and Rarity.objects.exists()

        if not db_has_data:
            # Sincronización inicial solo si está totalmente vacío
            sync_api_filter_values()

        # Construimos el diccionario usando .values_list para ahorrar memoria
        # No guardes objetos QuerySet en caché, guarda strings/listas simples
        filters = {
            "supertypes": list(
                Supertype.objects.values_list("display_name", flat=True).order_by("display_name")
            ),
            "subtypes": list(
                Subtype.objects.values_list("display_name", flat=True).order_by("display_name")
            ),
            "rarities": list(
                Rarity.objects.values_list("display_name", flat=True).order_by("display_name")
            ),
            "artists": list(Artist.objects.values_list("name", flat=True).order_by("name")),
        }
        cache.set(CACHE_KEY, filters, CACHE_TTL_SECONDS)

    if filter_name:
        return filters.get(filter_name)
    return filters
