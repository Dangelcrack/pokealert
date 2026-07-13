"""Tests para cards/services/search_service.py."""

import json
from unittest.mock import patch

import pytest

from cards.models import Card, Rarity
from cards.services.search_service import (
    build_search_query,
    buscar_cartas,
    safe_append,
)

# ==========================================
# safe_append / build_search_query
# ==========================================


@pytest.mark.django_db
def test_safe_append_ignora_id_no_numerico():
    """Un id no numérico no debe añadir nada a query_parts."""
    query_parts = []
    safe_append(query_parts, Rarity, "no-es-un-numero", "rarity", "name")
    assert query_parts == []


@pytest.mark.django_db
def test_safe_append_ignora_id_inexistente():
    """Un id numérico pero que no existe en la DB no debe añadir nada."""
    query_parts = []
    safe_append(query_parts, Rarity, "9999", "rarity", "name")
    assert query_parts == []


@pytest.mark.django_db
def test_safe_append_agrega_filtro_valido():
    """Un id válido y existente debe añadir el fragmento de query Lucene."""
    rarity = Rarity.objects.create(name="rare holo", display_name="Rare Holo")
    query_parts = []
    safe_append(query_parts, Rarity, str(rarity.id), "rarity", "name")
    assert query_parts == ['rarity:"rare holo"']


@pytest.mark.django_db
def test_build_search_query_combina_nombre_y_filtros():
    """Debe combinar el término de búsqueda con los filtros usando AND."""
    rarity = Rarity.objects.create(name="rare", display_name="Rare")
    query = build_search_query("Pikachu", rarity=str(rarity.id))
    assert "name:pikachu" in query
    assert 'rarity:"rare"' in query
    assert " AND " in query


def test_build_search_query_sin_nada_devuelve_cadena_vacia():
    """Sin query_raw ni filtros, debe devolver una cadena vacía."""
    assert build_search_query("") == ""


# ==========================================
# buscar_cartas (orquestador)
# ==========================================


@pytest.mark.django_db
def test_buscar_cartas_encuentra_resultado_en_db_local():
    """Una carta que coincide por nombre en la DB local debe aparecer en los resultados,
    aunque la API externa y el JSON local no devuelvan nada."""
    Card.objects.create(
        pokemontcg_id="base1-4",
        name="Charizard",
        image_url="https://example.com/img.png",
        price=100.0,
    )

    with (
        patch("cards.services.search_service.fetch_cards", return_value=[]),
        patch("cards.services.search_service._buscar_en_json_local", return_value={}),
    ):
        resultado = buscar_cartas(query_raw="Charizard")

    assert len(resultado["results"]) == 1
    assert resultado["results"][0]["name"] == "Charizard"


@pytest.mark.django_db
def test_buscar_cartas_sin_resultados_devuelve_lista_vacia():
    """Sin coincidencias en ninguna fuente, results debe quedar vacío y total_pages=1."""
    with (
        patch("cards.services.search_service.fetch_cards", return_value=[]),
        patch("cards.services.search_service._buscar_en_json_local", return_value={}),
    ):
        resultado = buscar_cartas(query_raw="carta-que-no-existe-en-ningun-sitio")

    assert resultado["results"] == []
    assert resultado["total_pages"] == 1
    assert resultado["has_next"] is False


@pytest.mark.django_db
def test_buscar_cartas_pagina_correctamente():
    """Con más de PAGE_SIZE resultados, debe paginar y marcar has_next=True en la página 1."""
    for i in range(30):
        Card.objects.create(
            pokemontcg_id=f"pikachu-{i}",
            name="Pikachu",
            image_url="https://example.com/img.png",
            price=10.0 + i,
        )

    with (
        patch("cards.services.search_service.fetch_cards", return_value=[]),
        patch("cards.services.search_service._buscar_en_json_local", return_value={}),
    ):
        pagina_1 = buscar_cartas(query_raw="Pikachu", current_page=1)
        pagina_2 = buscar_cartas(query_raw="Pikachu", current_page=2)

    assert len(pagina_1["results"]) == 24  # PAGE_SIZE
    assert pagina_1["has_next"] is True
    assert pagina_1["has_previous"] is False

    assert len(pagina_2["results"]) == 6  # resto
    assert pagina_2["has_previous"] is True


@pytest.mark.django_db
def test_buscar_cartas_ordena_por_precio_ascendente():
    """selected_sort='price' debe ordenar de menor a mayor precio."""
    Card.objects.create(
        pokemontcg_id="caro",
        name="Pikachu Caro",
        image_url="https://example.com/img.png",
        price=100.0,
    )
    Card.objects.create(
        pokemontcg_id="barato",
        name="Pikachu Barato",
        image_url="https://example.com/img.png",
        price=5.0,
    )

    with (
        patch("cards.services.search_service.fetch_cards", return_value=[]),
        patch("cards.services.search_service._buscar_en_json_local", return_value={}),
    ):
        resultado = buscar_cartas(query_raw="Pikachu", selected_sort="price")

    precios = [r["price"] for r in resultado["results"]]
    assert precios == sorted(precios)


@pytest.mark.django_db
def test_buscar_cartas_fallback_a_set_reciente_sin_query_ni_resultados():
    """Sin query y sin resultados en ninguna fuente, debe intentar el fallback de set reciente."""
    fallback_card = {
        "id": "sv01-1",
        "name": "Sprigatito",
        "images": {"small": "https://example.com/sprigatito.png"},
    }

    def fake_fetch(query, *args, **kwargs):
        if query == "set.id:sv01":
            return [fallback_card]
        return []

    with (
        patch("cards.services.search_service.fetch_cards", side_effect=fake_fetch),
        patch("cards.services.search_service._buscar_en_json_local", return_value={}),
    ):
        resultado = buscar_cartas(query_raw="")

    assert len(resultado["results"]) == 1
    assert resultado["results"][0]["name"] == "Sprigatito"


@pytest.mark.django_db
def test_buscar_en_json_local_no_pisa_resultados_de_db(tmp_path, settings):
    """El JSON local debe rellenar huecos pero nunca sobrescribir una carta
    ya encontrada en la DB local (comportamiento setdefault)."""
    Card.objects.create(
        pokemontcg_id="pikachu-1",
        name="Pikachu (DB)",
        image_url="https://example.com/db.png",
        price=50.0,
    )

    settings.BASE_DIR = tmp_path
    json_path = tmp_path / "todas_las_cartas_tcg.json"
    json_path.write_text(
        json.dumps(
            {
                "data": [
                    {"id": "pikachu-1", "name": "Pikachu (JSON - NO debería usarse)"},
                    {"id": "pikachu-2", "name": "Pikachu (solo en JSON)"},
                ]
            }
        ),
        encoding="utf-8",
    )

    with patch("cards.services.search_service.fetch_cards", return_value=[]):
        resultado = buscar_cartas(query_raw="Pikachu")

    nombres = {r["name"] for r in resultado["results"]}
    assert "Pikachu (DB)" in nombres
    assert "Pikachu (JSON - NO debería usarse)" not in nombres
