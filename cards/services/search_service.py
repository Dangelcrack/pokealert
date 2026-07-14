"""Servicio de búsqueda de cartas.

Combina tres fuentes de datos (DB local, API externa de Pokémon TCG, y
JSON estático de respaldo) en un único resultado deduplicado, aplicando
filtros, orden y paginación con optimización extrema de imágenes de catálogo.
"""

import json
import logging
import math
import os

from django.conf import settings
from django.db.models import Q
from cards.models import Artist, Card, Rarity, Subtype, Supertype
from cards.services.card_formatter import format_card
from cards.services.card_service import resolve_card_relations
from cards.services.pokemontcg_service import fetch_cards
from cards.services.pricing import extract_market_price
from cards.services.text_utils import get_expanded_search_terms, normalize

logger = logging.getLogger(__name__)

PAGE_SIZE = 24


def _optimizar_url_imagen(url: str, ancho: int = 150) -> str:
    """Utiliza el proxy CDN wsrv.nl para redimensionar y convertir a WebP.

    Esto reduce drásticamente el peso de las imágenes externas (de ~200 KB a ~8 KB).
    Se usa un ancho de 150px (aprox. 2x el tamaño de renderizado de 72px) para
    garantizar nitidez en pantallas Retina sin penalizar el rendimiento.
    """
    if not url:
        return ""
    # Si la URL ya es de wsrv.nl o local, no la modificamos
    if "wsrv.nl" in url or url.startswith("/"):
        return url

    # Limpiamos el protocolo de la URL de origen
    clean_url = url.replace("https://", "").replace("http://", "")
    return f"https://wsrv.nl/?url={clean_url}&w={ancho}&output=webp&q=80"


def safe_append(query_parts, model, id_value, label, field):
    """Evita que IDs vacíos o inválidos rompan la construcción de la consulta.

    Si `id_value` no es un entero válido o el objeto no existe, la función
    no modifica `query_parts` y devuelve silenciosamente."""
    if not id_value or not str(id_value).isdigit():
        return
    try:
        obj = model.objects.get(id=id_value)
        query_parts.append(f'{label}:"{getattr(obj, field)}"')
    except (model.DoesNotExist, ValueError, TypeError):
        return


def build_search_query(
    query_raw: str, rarity=None, supertype=None, subtype=None, artist=None
) -> str:
    """Construye una consulta Lucene para la API externa a partir de filtros."""
    query_parts = []

    if query_raw:
        expanded_terms = get_expanded_search_terms(query_raw)
        name_conditions = []
        for term in expanded_terms:
            if " " in term:
                name_conditions.append(f'name:"{term}"')
            else:
                name_conditions.append(f"name:{term}")

        if name_conditions:
            query_parts.append(f"({' OR '.join(name_conditions)})")

    if rarity:
        safe_append(query_parts, Rarity, rarity, "rarity", "name")
    if supertype:
        safe_append(query_parts, Supertype, supertype, "supertype", "name")
    if subtype:
        safe_append(query_parts, Subtype, subtype, "subtypes", "name")
    if artist:
        safe_append(query_parts, Artist, artist, "artist", "name")

    return " AND ".join(query_parts)


def _buscar_en_db_local(query_raw, rarity_id, supertype_id, subtype_id, artist_id) -> dict:
    """Busca en la base de datos local aplicando los mismos filtros que la API."""
    unique_cards_map = {}

    tiene_filtros = query_raw or rarity_id or supertype_id or subtype_id or artist_id
    if not tiene_filtros:
        return unique_cards_map

    db_filters = Q()
    if query_raw:
        target_terms = get_expanded_search_terms(query_raw)
        name_q = Q()
        for term in target_terms:
            name_q |= Q(name__icontains=term)
        db_filters &= name_q

    if rarity_id and str(rarity_id).isdigit():
        db_filters &= Q(rarity_id=rarity_id)
    if supertype_id and str(supertype_id).isdigit():
        db_filters &= Q(supertype_id=supertype_id)
    if subtype_id and str(subtype_id).isdigit():
        db_filters &= Q(subtype_id=subtype_id)
    if artist_id and str(artist_id).isdigit():
        db_filters &= Q(artist_id=artist_id)

    db_results = Card.objects.filter(db_filters).select_related(
        "rarity", "supertype", "subtype", "artist"
    )[:150]

    for c in db_results:
        # Optimizamos la miniatura para la búsqueda y preservamos la original para la vista detalle
        img_small_opt = _optimizar_url_imagen(c.image_url)
        unique_cards_map[c.pokemontcg_id] = {
            "id": c.pokemontcg_id,
            "name": c.name,
            "image_url": img_small_opt,
            "images": {"small": img_small_opt, "large": c.image_url},
            "price": float(c.price or 0.0),
            "set_name": c.set_name,
            "set": {"name": c.set_name or "Desconocido", "series": ""},
            "number": c.number or "N/A",
            "rarity": c.rarity.display_name if c.rarity else "N/A",
            "supertype": c.supertype.display_name if c.supertype else "N/A",
            "subtypes": [c.subtype.display_name] if c.subtype else ["N/A"],
            "artist": c.artist.name if c.artist else "Desconocido",
        }

    return unique_cards_map


def _buscar_en_api_externa(api_query: str) -> dict:
    """Consulta la API externa de Pokémon TCG. Devuelve `{}` si falla o está vacía."""
    unique_cards_map = {}
    if not api_query:
        return unique_cards_map

    try:
        api_data = fetch_cards(api_query)
        if api_data:
            for card in api_data:
                cid = card.get("id")
                if cid:
                    unique_cards_map[cid] = card
    except Exception as e:
        logger.warning(f"API Externa no disponible o falló temporalmente: {e}")

    return unique_cards_map


def _buscar_en_json_local(query_raw, rarity_id, supertype_id, subtype_id, artist_id) -> dict:
    """Busca en el JSON estático de respaldo aplicando los mismos filtros."""
    unique_cards_map = {}
    json_path = os.path.join(settings.BASE_DIR, "todas_las_cartas_tcg.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data_cargada = json.load(f)
    except Exception as e:
        logger.warning(f"No se pudo procesar el JSON local ({e}).")
        return unique_cards_map

    local_cards = (
        data_cargada.get("data", list(data_cargada.values()))
        if isinstance(data_cargada, dict)
        else data_cargada
    )

    target_terms = get_expanded_search_terms(query_raw) if query_raw else set()
    target_rarity = (
        Rarity.objects.filter(id=rarity_id).first().name
        if rarity_id and str(rarity_id).isdigit()
        else None
    )
    target_supertype = (
        Supertype.objects.filter(id=supertype_id).first().name
        if supertype_id and str(supertype_id).isdigit()
        else None
    )
    target_subtype = (
        Subtype.objects.filter(id=subtype_id).first().name
        if subtype_id and str(subtype_id).isdigit()
        else None
    )
    target_artist = (
        Artist.objects.filter(id=artist_id).first().name
        if artist_id and str(artist_id).isdigit()
        else None
    )

    for card in local_cards:
        match = True
        if target_terms:
            card_name = card.get("name", "").lower()
            if not any(term in card_name for term in target_terms):
                match = False
        if target_rarity and normalize(card.get("rarity")) != normalize(target_rarity):
            match = False
        if target_supertype and normalize(card.get("supertype")) != normalize(target_supertype):
            match = False
        if target_artist and normalize(card.get("artist")) != normalize(target_artist):
            match = False
        if target_subtype:
            subtypes_list = card.get("subtypes", [])
            if isinstance(subtypes_list, str):
                subtypes_list = [subtypes_list]
            if not any(normalize(st) == normalize(target_subtype) for st in subtypes_list):
                match = False

        if match:
            cid = card.get("id") or card.get("pokemontcg_id")
            if cid and cid not in unique_cards_map:
                unique_cards_map[cid] = card

    return unique_cards_map


def _fallback_set_reciente() -> dict:
    """Devuelve cartas de un set reciente cuando no hay resultados ni query."""
    unique_cards_map = {}
    try:
        api_data = fetch_cards("set.id:sv01")
        for card in api_data:
            unique_cards_map[card.get("id")] = card
    except Exception:
        pass
    return unique_cards_map


def _ordenar(all_cards: list, selected_sort: str) -> None:
    """Ordena `all_cards` in-place según `selected_sort` ('price', '-price', 'name')."""
    if selected_sort in ["price", "-price"]:
        all_cards.sort(
            key=lambda x: float(
                extract_market_price(x.get("tcgplayer", {}).get("prices", {}))
                if x.get("tcgplayer")
                else (x.get("price") or 0.0)
            ),
            reverse=(selected_sort == "-price"),
        )
    elif selected_sort == "name":
        all_cards.sort(key=lambda x: x.get("name", ""))


def _formatear_pagina(page_cards: list) -> list:
    """Resuelve relaciones, aplica optimización de imágenes y formatea la página actual."""
    results = []
    for card_data in page_cards:
        relations = resolve_card_relations(card_data)
        card_formatted = format_card(card_data)

        # 1. Extraer y optimizar la URL de la imagen de miniatura
        raw_img = (
            card_data.get("images", {}).get("small")
            or card_data.get("image_url")
            or card_data.get("image_url_small")
            or card_data.get("image")
            or ""
        )

        # Guardamos la versión optimizada ligera para la búsqueda
        opt_img = _optimizar_url_imagen(raw_img)
        card_formatted["image_url"] = opt_img
        card_formatted["images"] = {
            "small": opt_img,
            "large": raw_img,  # Mantener la original de alta resolución por si se necesita
        }

        if not card_formatted.get("set_name") or card_formatted.get("set_name") == "Unknown":
            card_formatted["set_name"] = card_data.get("set_name") or card_data.get("set", {}).get(
                "name", "Unknown"
            )
        if not card_formatted.get("price"):
            card_formatted["price"] = (
                extract_market_price(card_data.get("tcgplayer", {}).get("prices", {}))
                if card_data.get("tcgplayer")
                else card_data.get("price")
            )

        if relations.get("rarity"):
            card_formatted["rarity"] = relations["rarity"].display_name
        if relations.get("artist"):
            card_formatted["artist"] = relations["artist"].name
        if relations.get("supertype"):
            card_formatted["supertype"] = relations["supertype"].display_name

        card_formatted["id"] = (
            card_data.get("id") or card_data.get("pokemontcg_id") or card_data.get("card_id")
        )
        results.append(card_formatted)
    return results


def buscar_cartas(
    query_raw: str = "",
    selected_sort: str = "",
    rarity_id: str = "",
    supertype_id: str = "",
    subtype_id: str = "",
    artist_id: str = "",
    current_page: int = 1,
) -> dict:
    """Orquesta la búsqueda combinando las tres fuentes de datos.

    Devuelve un dict con `results` (lista de cartas formateadas de la página
    actual), `total_pages`, `has_next` y `has_previous`."""
    api_query = build_search_query(query_raw, rarity_id, supertype_id, subtype_id, artist_id)

    unique_cards_map = {}
    unique_cards_map.update(
        _buscar_en_db_local(query_raw, rarity_id, supertype_id, subtype_id, artist_id)
    )
    unique_cards_map.update(_buscar_en_api_externa(api_query))

    # El JSON local solo rellena huecos: no pisa nada ya encontrado
    for cid, card in _buscar_en_json_local(
        query_raw, rarity_id, supertype_id, subtype_id, artist_id
    ).items():
        unique_cards_map.setdefault(cid, card)

    if not unique_cards_map and not query_raw:
        unique_cards_map.update(_fallback_set_reciente())

    all_cards = list(unique_cards_map.values())
    for card_data in all_cards:
        resolve_card_relations(card_data)

    if not all_cards:
        return {
            "results": [],
            "total_pages": 1,
            "has_next": False,
            "has_previous": current_page > 1,
        }

    _ordenar(all_cards, selected_sort)

    total_count = len(all_cards)
    total_pages = math.ceil(total_count / PAGE_SIZE)
    start = (current_page - 1) * PAGE_SIZE
    page_cards = all_cards[start : start + PAGE_SIZE]

    results = _formatear_pagina(page_cards)

    return {
        "results": results,
        "total_pages": total_pages,
        "has_next": current_page < total_pages,
        "has_previous": current_page > 1,
    }
