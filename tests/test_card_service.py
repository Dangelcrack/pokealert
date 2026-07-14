"""Tests para cards/services/card_service.py."""

import json

import pytest

from cards.models import Artist, Rarity, Subtype, Supertype
from cards.services.card_service import get_local_card_by_id, resolve_card_relations


@pytest.mark.django_db
def test_resolve_card_relations_crea_rarity_si_no_existe():
    """Si la rareza no existe en la DB, debe crearse con el name
    normalizado."""
    relations = resolve_card_relations({"rarity": "Rare Holo"})

    assert relations["rarity"].display_name == "Rare Holo"
    assert Rarity.objects.filter(name="rare holo").exists()


@pytest.mark.django_db
def test_resolve_card_relations_reutiliza_rarity_existente():
    """Si la rareza ya existe (mismo name normalizado), no debe duplicarse."""
    Rarity.objects.create(name="rare holo", display_name="Rare Holo")

    resolve_card_relations({"rarity": "Rare Holo"})

    assert Rarity.objects.filter(name="rare holo").count() == 1


@pytest.mark.django_db
def test_resolve_card_relations_crea_supertype_y_subtype():
    """Debe crear Supertype y Subtype (usando el primer elemento de la lista)
    si vienen en el payload."""
    relations = resolve_card_relations({"supertype": "Pokémon", "subtypes": ["Basic", "EX"]})

    assert relations["supertype"].display_name == "Pokémon"
    assert relations["subtype"].display_name == "Basic"
    assert Supertype.objects.filter(name="pokemon").exists()
    assert Subtype.objects.filter(name="basic").exists()
    # El segundo subtype de la lista no debe crearse, solo el primero
    assert not Subtype.objects.filter(name="ex").exists()


@pytest.mark.django_db
def test_resolve_card_relations_crea_artist():
    """Debe crear el Artist si viene en el payload."""
    relations = resolve_card_relations({"artist": "Ken Sugimori"})

    assert relations["artist"].name == "Ken Sugimori"
    assert Artist.objects.filter(name="Ken Sugimori").exists()


@pytest.mark.django_db
def test_resolve_card_relations_con_payload_vacio_no_crea_nada():
    """Un payload sin campos relevantes no debe crear ninguna relación."""
    relations = resolve_card_relations({})

    assert relations == {}
    assert Rarity.objects.count() == 0
    assert Artist.objects.count() == 0


def test_get_local_card_by_id_encuentra_carta_por_id(tmp_path, settings):
    """Debe encontrar una carta en el JSON local buscando por 'id'."""
    settings.BASE_DIR = tmp_path
    json_path = tmp_path / "todas_las_cartas_tcg.json"
    json_path.write_text(
        json.dumps({"data": [{"id": "sv1-1", "name": "Sprigatito"}]}), encoding="utf-8"
    )

    card = get_local_card_by_id("sv1-1")

    assert card is not None
    assert card["name"] == "Sprigatito"


def test_get_local_card_by_id_devuelve_none_si_no_existe_archivo(tmp_path, settings):
    """Si el JSON local no existe, debe devolver None sin lanzar excepción."""
    settings.BASE_DIR = tmp_path

    card = get_local_card_by_id("cualquier-id")

    assert card is None


def test_get_local_card_by_id_devuelve_none_si_no_encuentra_la_carta(tmp_path, settings):
    """Si el JSON existe pero no contiene ese id, debe devolver None."""
    settings.BASE_DIR = tmp_path
    json_path = tmp_path / "todas_las_cartas_tcg.json"
    json_path.write_text(json.dumps({"data": [{"id": "otra-carta"}]}), encoding="utf-8")

    card = get_local_card_by_id("no-existe")

    assert card is None
