"""Tests para cards/services/card_detail_service.py."""

from unittest.mock import patch

import pytest
from django.core.cache import cache

from alerts.models import PriceHistory
from cards.models import Card
from cards.services.card_detail_service import _cache_key, obtener_contexto_card_detail


@pytest.fixture(autouse=True)
def limpiar_cache():
    """Evita que la caché de detalle de carta se filtre entre tests."""
    yield
    cache.clear()


@pytest.mark.django_db
def test_card_id_vacio_devuelve_error_sin_tocar_nada():
    """Un card_id vacío debe devolver el error de validación sin llegar a la DB ni a la API."""
    with patch("cards.services.card_detail_service.fetch_card") as mock_fetch:
        contexto = obtener_contexto_card_detail("")
        mock_fetch.assert_not_called()

    assert contexto["error"] == "Identificador de carta no válido."
    assert contexto["card"] == {}


@pytest.mark.django_db
def test_datos_locales_validos_no_llama_a_la_api():
    """Si la carta local tiene imagen, set_name válido y precio > 0, no debe llamar a fetch_card."""
    Card.objects.create(
        pokemontcg_id="base1-4",
        name="Charizard",
        image_url="https://example.com/charizard.png",
        set_name="Base Set",
        price=150.0,
    )

    with patch("cards.services.card_detail_service.fetch_card") as mock_fetch:
        contexto = obtener_contexto_card_detail("base1-4")
        mock_fetch.assert_not_called()

    assert contexto["error"] is None
    assert contexto["card"]["name"] == "Charizard"
    assert contexto["market_price"] == "150.00"


@pytest.mark.django_db
def test_datos_locales_incompletos_dispara_llamada_a_la_api():
    """Si la carta local existe pero le falta la imagen, debe considerarse inválida y
    escalar a la API externa (o al JSON local, que aquí forzamos a fallar)."""
    Card.objects.create(
        pokemontcg_id="base1-5",
        name="Blastoise",
        image_url="",  # dato incompleto -> is_local_data_valid=False
        set_name="Base Set",
        price=120.0,
    )

    api_response = {
        "id": "base1-5",
        "name": "Blastoise",
        "images": {"small": "https://example.com/blastoise.png"},
        "set": {"name": "Base Set"},
        "tcgplayer": {"prices": {"normal": {"market": 130.0}}},
    }

    with (
        patch("cards.services.card_detail_service.get_local_card_by_id", return_value=None),
        patch(
            "cards.services.card_detail_service.fetch_card", return_value=api_response
        ) as mock_fetch,
    ):
        contexto = obtener_contexto_card_detail("base1-5")
        mock_fetch.assert_called_once_with("base1-5")

    assert contexto["error"] is None
    assert contexto["card"]["price"] == 130.0


@pytest.mark.django_db
def test_carta_inexistente_localmente_usa_json_local_antes_que_la_api():
    """Si get_local_card_by_id encuentra la carta, no debe llamarse a fetch_card."""
    json_card = {
        "id": "sv1-1",
        "name": "Sprigatito",
        "images": {"small": "https://example.com/sprigatito.png"},
        "set": {"name": "Scarlet & Violet"},
        "price": 8.0,
    }

    with (
        patch("cards.services.card_detail_service.get_local_card_by_id", return_value=json_card),
        patch("cards.services.card_detail_service.fetch_card") as mock_fetch,
    ):
        contexto = obtener_contexto_card_detail("sv1-1")
        mock_fetch.assert_not_called()

    assert contexto["error"] is None
    assert contexto["card"]["name"] == "Sprigatito"


@pytest.mark.django_db
def test_api_y_json_local_fallan_devuelve_error():
    """Si ni el JSON local ni la API encuentran la carta, debe devolver un error descriptivo."""
    with (
        patch("cards.services.card_detail_service.get_local_card_by_id", return_value=None),
        patch("cards.services.card_detail_service.fetch_card", return_value=None),
    ):
        contexto = obtener_contexto_card_detail("no-existe-en-ningun-lado")

    assert contexto["error"] is not None
    assert contexto["card"] == {}


@pytest.mark.django_db
def test_api_lanza_excepcion_devuelve_error_sin_reventar():
    """Si fetch_card lanza una excepción, el servicio debe capturarla y devolver un error, no propagarla."""
    with (
        patch("cards.services.card_detail_service.get_local_card_by_id", return_value=None),
        patch("cards.services.card_detail_service.fetch_card", side_effect=Exception("API caída")),
    ):
        contexto = obtener_contexto_card_detail("carta-problematica")

    assert contexto["error"] is not None
    assert "API caída" in contexto["error"]


@pytest.mark.django_db
def test_crea_price_history_si_no_existe_hoy():
    """Al obtener el detalle de una carta con precio válido, debe crearse un
    punto de PriceHistory para hoy si todavía no existe uno."""
    card = Card.objects.create(
        pokemontcg_id="base1-6",
        name="Venusaur",
        image_url="https://example.com/venusaur.png",
        set_name="Base Set",
        price=90.0,
    )
    assert PriceHistory.objects.filter(card=card).count() == 0

    obtener_contexto_card_detail("base1-6")

    assert PriceHistory.objects.filter(card=card).count() == 1


@pytest.mark.django_db
def test_no_duplica_price_history_si_ya_existe_hoy():
    """Si ya hay un PriceHistory de hoy para la carta, no debe crear uno nuevo."""
    card = Card.objects.create(
        pokemontcg_id="base1-7",
        name="Mewtwo",
        image_url="https://example.com/mewtwo.png",
        set_name="Base Set",
        price=200.0,
    )
    PriceHistory.objects.create(card=card, price=200.0)
    assert PriceHistory.objects.filter(card=card).count() == 1

    obtener_contexto_card_detail("base1-7")

    assert PriceHistory.objects.filter(card=card).count() == 1


@pytest.mark.django_db
def test_segunda_llamada_usa_cache_sin_tocar_la_db_de_relaciones():
    """La segunda llamada al mismo card_id debe servirse desde caché."""
    Card.objects.create(
        pokemontcg_id="base1-8",
        name="Alakazam",
        image_url="https://example.com/alakazam.png",
        set_name="Base Set",
        price=40.0,
    )

    contexto_1 = obtener_contexto_card_detail("base1-8")
    assert cache.get(_cache_key("base1-8")) is not None

    with patch("cards.services.card_detail_service.fetch_card") as mock_fetch:
        contexto_2 = obtener_contexto_card_detail("base1-8")
        mock_fetch.assert_not_called()

    assert contexto_1["card"]["name"] == contexto_2["card"]["name"]
