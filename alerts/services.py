"""Servicio de gestión de alertas de precio.

Contiene la lógica de negocio para crear y actualizar `PriceAlert`,
incluyendo la sincronización de la carta si aún no existe localmente.
"""

from cards.models import Card
from cards.services.card_formatter import format_card
from cards.services.card_service import resolve_card_relations
from cards.services.pokemontcg_service import fetch_card

from .models import PriceAlert


class AlertaSinPrecioValidoError(Exception):
    """Se lanza cuando no hay un precio válido para calcular la alerta."""


class CartaNoEncontradaError(Exception):
    """Se lanza cuando la carta no existe localmente ni se pudo obtener de la
    API."""


def crear_alerta(
    user, pokemontcg_id: str, discount_percentage: str, current_price_str: str
) -> PriceAlert:
    """Crea una `PriceAlert` para el usuario, sincronizando la carta si hace
    falta.

    Lanza `AlertaSinPrecioValidoError` si faltan datos de precio, o
    `CartaNoEncontradaError` si la carta no se pudo obtener de la API.
    """
    if not pokemontcg_id or not discount_percentage or current_price_str == "N/A":
        raise AlertaSinPrecioValidoError("No se puede crear una alerta sin un precio válido.")

    discount = int(discount_percentage)
    current_price = float(current_price_str)
    target_price = current_price * (1 - (discount / 100))

    card = Card.objects.filter(pokemontcg_id=pokemontcg_id).first()
    if not card:
        card_data = fetch_card(pokemontcg_id)
        if not card_data:
            raise CartaNoEncontradaError("No se pudo obtener la carta de la API.")

        relations = resolve_card_relations(card_data)
        formatted = format_card(card_data)
        card = Card.objects.create(
            pokemontcg_id=pokemontcg_id,
            name=formatted.get("name"),
            image_url=formatted.get("image_url") or formatted.get("images", {}).get("small", ""),
            set_name=formatted.get("set_name"),
            number=formatted.get("number"),
            price=formatted.get("price") or current_price,
            **relations,
        )

    return PriceAlert.objects.create(
        user=user,
        card=card,
        discount_percentage=discount,
        target_price=round(target_price, 2),
        is_active=True,
    )


def actualizar_descuento_alerta(alert: PriceAlert, discount_percentage: str) -> PriceAlert:
    """Actualiza el porcentaje de descuento de una alerta y recalcula su
    `target_price`.

    Devuelve la misma instancia de `alert`, ya guardada. No hace nada si
    `discount_percentage` no es un dígito válido.
    """
    if not discount_percentage or not str(discount_percentage).isdigit():
        return alert

    nuevo_porcentaje = int(discount_percentage)
    precio_base = float(alert.card.price or 0.0)

    alert.discount_percentage = nuevo_porcentaje
    alert.target_price = precio_base * (1.0 - (nuevo_porcentaje / 100.0))
    alert.save()
    return alert
