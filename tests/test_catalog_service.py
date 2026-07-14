"""Tests para cards/services/catalog_service.py."""

from unittest.mock import patch

import pytest
from django.core.cache import cache

from cards.models import Artist, Rarity, Subtype, Supertype
from cards.services.catalog_service import (
    CACHE_KEY,
    get_filter_options,
    invalidate_filter_options_cache,
    sync_api_filter_values,
)


@pytest.fixture(autouse=True)
def limpiar_cache():
    """Limpia la caché de opciones de filtro antes y después de cada test, para
    que un test no contamine al siguiente."""
    cache.delete(CACHE_KEY)
    yield
    cache.delete(CACHE_KEY)


@pytest.mark.django_db
def test_sync_api_filter_values_crea_registros_desde_la_api_mockeada():
    """sync_api_filter_values debe crear Rarity/Supertype/Subtype a partir de
    lo que devuelva la API externa (mockeada aquí, sin red real)."""

    def fake_api(filter_type):
        return {
            "supertypes": ["Pokémon", "Trainer"],
            "subtypes": ["Basic", "Stage 1"],
            "rarities": ["Common", "Rare"],
        }[filter_type]

    with patch("cards.services.catalog_service.get_api_filter_options", side_effect=fake_api):
        sync_api_filter_values()

    assert Supertype.objects.filter(name="pokemon").exists()
    assert Subtype.objects.filter(name="basic").exists()
    assert Rarity.objects.filter(name="common").exists()


@pytest.mark.django_db
def test_sync_api_filter_values_ignora_labels_vacios():
    """Un label vacío o None en la respuesta de la API no debe intentar crear
    un registro."""

    def fake_api(filter_type):
        return {"supertypes": ["", None, "Pokémon"], "subtypes": [], "rarities": []}[filter_type]

    with patch("cards.services.catalog_service.get_api_filter_options", side_effect=fake_api):
        sync_api_filter_values()

    assert Supertype.objects.count() == 1
    assert Supertype.objects.first().display_name == "Pokémon"


@pytest.mark.django_db
def test_get_filter_options_sincroniza_si_db_incompleta():
    """Si la DB tiene menos registros de los esperados, debe disparar la
    sincronización."""

    def fake_api(filter_type):
        # Suficientes para superar el umbral de "DB completa" en get_filter_options
        counts = {"supertypes": 3, "subtypes": 20, "rarities": 20}
        return [f"{filter_type}-{i}" for i in range(counts[filter_type])]

    with patch("cards.services.catalog_service.get_api_filter_options", side_effect=fake_api):
        result = get_filter_options()

    assert len(result["supertypes"]) == 3
    assert len(result["rarities"]) == 20
    assert "artists" in result


@pytest.mark.django_db
def test_get_filter_options_usa_cache_si_db_ya_completa():
    """Si la DB ya está completa, la segunda llamada debe usar caché sin volver
    a llamar a la API."""
    for i in range(3):
        Supertype.objects.create(name=f"st{i}", display_name=f"ST{i}")
    for i in range(20):
        Subtype.objects.create(name=f"sub{i}", display_name=f"Sub{i}")
        Rarity.objects.create(name=f"rar{i}", display_name=f"Rar{i}")

    with patch("cards.services.catalog_service.get_api_filter_options") as mock_api:
        get_filter_options()
        mock_api.reset_mock()

        get_filter_options()
        mock_api.assert_not_called()


@pytest.mark.django_db
def test_get_filter_options_con_filter_name_devuelve_subconjunto():
    """Pasar filter_name debe devolver solo esa lista, no el dict completo."""

    def fake_api(filter_type):
        counts = {"supertypes": 3, "subtypes": 20, "rarities": 20}
        return [f"{filter_type}-{i}" for i in range(counts[filter_type])]

    with patch("cards.services.catalog_service.get_api_filter_options", side_effect=fake_api):
        artistas = get_filter_options("artists")

    assert artistas == list(Artist.objects.all().order_by("name"))


@pytest.mark.django_db
def test_invalidate_filter_options_cache_borra_la_entrada():
    """invalidate_filter_options_cache debe eliminar la clave de caché."""
    cache.set(CACHE_KEY, {"fake": "data"}, 3600)

    invalidate_filter_options_cache()

    assert cache.get(CACHE_KEY) is None
