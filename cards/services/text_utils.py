"""Utilidades de normalización y expansión de texto para búsqueda.

Funciones puras (sin dependencia de request/response) usadas para comparar,
normalizar y traducir términos de búsqueda entre español e inglés (TCG)."""

import unicodedata

from django.db.models import Q

from cards.models import PokemonEspecie
from cards.utils import POKEMON_ES_TO_TCG, TCG_TERMS


def normalize(text) -> str:
    """Normaliza una cadena para comparaciones: devuelve minúsculas sin acentos.

    Retorna una cadena vacía si la entrada es falsy. Utiliza NFD para separar
    diacríticos y filtra los caracteres de marca."""
    if not text:
        return ""
    text = str(text).lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def get_expanded_search_terms(query_raw: str) -> set:
    """Expande un término de búsqueda con sinónimos y traducciones relevantes.

    Devuelve un conjunto de términos en minúsculas que incluye la cadena
    original normalizada y coincidencias encontradas en los mapeos
    `POKEMON_ES_TO_TCG` y `TCG_TERMS`."""
    if not query_raw:
        return set()

    query_norm = normalize(query_raw)
    terms = {query_raw.strip().lower()}

    for es_key, en_value in POKEMON_ES_TO_TCG.items():
        if es_key.startswith(query_norm) or query_norm in es_key:
            terms.add(en_value.lower())

    for es_key, en_value in TCG_TERMS.items():
        if es_key.startswith(query_norm) or query_norm in es_key:
            terms.add(en_value.lower())

    return terms


def translate_query(query_raw: str) -> str:
    """Traduce un término de búsqueda desde español a su equivalente TCG (inglés).

    Busca coincidencias en el modelo `PokemonEspecie` y en los diccionarios de
    mapeo del proyecto. Si no encuentra traducción, devuelve el término original
    recortado."""
    if not query_raw:
        return ""
    q = normalize(query_raw)
    pokemon = PokemonEspecie.objects.filter(
        Q(name_es__icontains=q) | Q(name_en__icontains=q)
    ).first()
    if pokemon:
        return pokemon.name_en
    if q in TCG_TERMS:
        return TCG_TERMS[q]
    if q in POKEMON_ES_TO_TCG:
        return POKEMON_ES_TO_TCG[q]
    for es, en in POKEMON_ES_TO_TCG.items():
        if normalize(es).startswith(q):
            return en
    return query_raw.strip()
