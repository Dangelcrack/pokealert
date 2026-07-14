"""Tests para alerts/services.py."""

from unittest.mock import patch

import pytest

from alerts.models import PriceAlert
from alerts.services import (
    AlertaSinPrecioValidoError,
    CartaNoEncontradaError,
    actualizar_descuento_alerta,
    crear_alerta,
)
from cards.models import Card


@pytest.mark.django_db
def test_crear_alerta_con_carta_existente_calcula_target_price(test_user):
    """Si la carta ya existe localmente, no debe llamarse a la API externa."""
    Card.objects.create(
        pokemontcg_id="base1-4",
        name="Charizard",
        image_url="https://example.com/img.png",
        price=100.0,
    )

    with patch("alerts.services.fetch_card") as mock_fetch:
        alerta = crear_alerta(
            user=test_user,
            pokemontcg_id="base1-4",
            discount_percentage="20",
            current_price_str="100.0",
        )
        mock_fetch.assert_not_called()

    assert alerta.discount_percentage == 20
    assert alerta.target_price == 80.0
    assert alerta.card.pokemontcg_id == "base1-4"


@pytest.mark.django_db
def test_crear_alerta_sin_precio_valido_lanza_error(test_user):
    """Sin pokemontcg_id, discount_percentage o con current_price_str='N/A'
    debe fallar."""
    with pytest.raises(AlertaSinPrecioValidoError):
        crear_alerta(
            user=test_user,
            pokemontcg_id="base1-4",
            discount_percentage="20",
            current_price_str="N/A",
        )


@pytest.mark.django_db
def test_crear_alerta_sincroniza_carta_inexistente_con_la_api(test_user):
    """Si la carta no existe localmente, debe sincronizarla vía fetch_card."""
    card_data = {
        "id": "sv1-10",
        "name": "Sprigatito",
        "images": {"small": "https://example.com/sprigatito.png"},
        "tcgplayer": {"prices": {"normal": {"market": 5.0}}},
    }

    with patch("alerts.services.fetch_card", return_value=card_data):
        alerta = crear_alerta(
            user=test_user,
            pokemontcg_id="sv1-10",
            discount_percentage="10",
            current_price_str="5.0",
        )

    assert Card.objects.filter(pokemontcg_id="sv1-10").exists()
    assert alerta.card.name == "Sprigatito"


@pytest.mark.django_db
def test_crear_alerta_sin_datos_de_api_lanza_error(test_user):
    """Si la carta no existe localmente y la API no devuelve nada, debe fallar
    con CartaNoEncontradaError."""
    with patch("alerts.services.fetch_card", return_value=None):
        with pytest.raises(CartaNoEncontradaError):
            crear_alerta(
                user=test_user,
                pokemontcg_id="carta-inexistente",
                discount_percentage="10",
                current_price_str="5.0",
            )


@pytest.mark.django_db
def test_actualizar_descuento_alerta_recalcula_target_price(test_user):
    """Cambiar el descuento debe recalcular target_price sobre el precio actual
    de la carta."""
    card = Card.objects.create(
        pokemontcg_id="base1-5",
        name="Blastoise",
        image_url="https://example.com/img.png",
        price=200.0,
    )
    alert = PriceAlert.objects.create(
        user=test_user, card=card, discount_percentage=10, target_price=180.0
    )

    actualizado = actualizar_descuento_alerta(alert, "50")

    assert actualizado.discount_percentage == 50
    assert actualizado.target_price == 100.0


@pytest.mark.django_db
def test_actualizar_descuento_alerta_con_valor_invalido_no_cambia_nada(test_user):
    """Un discount_percentage no numérico no debe modificar la alerta."""
    card = Card.objects.create(
        pokemontcg_id="base1-6",
        name="Venusaur",
        image_url="https://example.com/img.png",
        price=150.0,
    )
    alert = PriceAlert.objects.create(
        user=test_user, card=card, discount_percentage=10, target_price=135.0
    )

    actualizar_descuento_alerta(alert, "no-es-un-numero")

    alert.refresh_from_db()
    assert alert.discount_percentage == 10
    assert alert.target_price == 135.0
