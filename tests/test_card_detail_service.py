from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.utils import timezone
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
    with patch("cards.services.card_detail_service.fetch_card") as mock_fetch:
        contexto = obtener_contexto_card_detail("")
        mock_fetch.assert_not_called()
    assert contexto["error"] == "Identificador de carta no válido."


@pytest.mark.django_db
def test_datos_locales_validos_no_llama_a_la_api():
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
    assert contexto["market_price"] == "150.00"


@pytest.mark.django_db(transaction=True)
def test_no_duplica_price_history_si_ya_existe_hoy():
    # 1. Preparación
    card = Card.objects.create(
        pokemontcg_id="base1-7",
        name="Mewtwo",
        image_url="https://example.com/mewtwo.png",
        set_name="Base Set",
        price=200.0,
    )

    hoy = timezone.localdate()

    PriceHistory.objects.create(card=card, price=200.0, date=hoy)

    todos = PriceHistory.objects.filter(card=card)
    print(f"Fechas en DB: {[p.date for p in todos]}")
    print(f"Fecha buscada: {hoy}")

    obtener_contexto_card_detail("base1-7")

    card.refresh_from_db()
    historicos = PriceHistory.objects.filter(card=card, date=hoy)

    assert (
        historicos.count() == 1
    ), f"Se esperaba 1 registro para la fecha {hoy}, pero se encontraron {historicos.count()}"
    assert historicos.first().price == 200.0


@pytest.mark.django_db
def test_segunda_llamada_usa_cache_sin_tocar_la_db_de_relaciones():
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
