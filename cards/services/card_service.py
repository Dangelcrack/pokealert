"""Servicio de resolución de datos de carta: relaciones y fuentes locales.

Contiene helpers para vincular (o crear) las entidades relacionadas de
una carta (rareza, supertype, subtype, artista, especie Pokémon) y para
leer cartas desde el JSON estático local usado como caché de respaldo.
"""

import json
import os

from django.conf import settings
from django.db.models import Q

from cards.models import Rarity, Supertype, Subtype, Artist, PokemonEspecie
from cards.services.catalog_service import invalidate_filter_options_cache
from cards.services.text_utils import normalize


def resolve_card_relations(card_data: dict) -> dict:
    """Resuelve y crea (si procede) las relaciones referenciales para una
    carta.

    Retorna un dict con instancias para `rarity`, `supertype`,
    `subtype`, `artist` y `pokemon_especie` cuando aplica. Invalida la
    caché de opciones de filtro si se generan nuevos registros.
    """
    relations = {}
    if card_data.get("rarity"):
        rarity, created = Rarity.objects.get_or_create(
            name=normalize(card_data["rarity"]),
            defaults={"display_name": card_data["rarity"]},
        )
        relations["rarity"] = rarity
        if created:
            invalidate_filter_options_cache()
    if card_data.get("supertype"):
        supertype, created = Supertype.objects.get_or_create(
            name=normalize(card_data["supertype"]),
            defaults={"display_name": card_data["supertype"]},
        )
        relations["supertype"] = supertype
        if created:
            invalidate_filter_options_cache()
    if card_data.get("subtypes") and isinstance(card_data["subtypes"], list):
        subtype_name = card_data["subtypes"][0] if card_data["subtypes"] else None
        if subtype_name:
            subtype, created = Subtype.objects.get_or_create(
                name=normalize(subtype_name), defaults={"display_name": subtype_name}
            )
            relations["subtype"] = subtype
            if created:
                invalidate_filter_options_cache()
    if card_data.get("artist"):
        artist, created = Artist.objects.get_or_create(name=card_data["artist"])
        relations["artist"] = artist
        if created:
            invalidate_filter_options_cache()
    if card_data.get("name"):
        pokemon = PokemonEspecie.objects.filter(
            Q(name_en__icontains=card_data["name"]) | Q(name_es__icontains=card_data["name"])
        ).first()
        if pokemon:
            relations["pokemon_especie"] = pokemon
    return relations


def get_local_card_by_id(card_id: str):
    """Recupera una carta desde el archivo JSON local
    `todas_las_cartas_tcg.json`.

    Busca por varios identificadores posibles (`id`, `pokemontcg_id`,
    `card_id`). Devuelve el diccionario de la carta o `None` si no
    existe o si el archivo no puede leerse correctamente.
    """
    json_path = os.path.join(settings.BASE_DIR, "todas_las_cartas_tcg.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    cards = data.get("data", list(data.values())) if isinstance(data, dict) else data
    for card in cards:
        if str(card.get("id") or card.get("pokemontcg_id") or card.get("card_id")) == str(card_id):
            return card
    return None
