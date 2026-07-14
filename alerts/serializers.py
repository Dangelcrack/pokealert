"""Serializadores de API para la aplicación `alerts`.

Define la serialización de `PriceAlert` y `PriceHistory` para los
endpoints de la API REST.
"""

from django.db import IntegrityError
from rest_framework import serializers

from cards.models import Card
from cards.serializers import CardSerializer
from cards.services.pokemontcg_service import fetch_card
from cards.services.pricing import extract_market_price

from .models import PriceAlert, PriceHistory
from .services import (
    AlertaSinPrecioValidoError,
    CartaNoEncontradaError,
    crear_alerta,
)


class PriceHistorySerializer(serializers.ModelSerializer):
    """Serializador read-only para el modelo `PriceHistory`.

    Incluye los campos mínimos necesarios para representar puntos del
    histórico en las APIs públicas o internas.
    """

    class Meta:
        """Meta para `PriceHistorySerializer` que define campos expuestos."""

        model = PriceHistory
        fields = ["id", "card", "price", "marketplace", "recorded_at"]


class PriceAlertSerializer(serializers.ModelSerializer):
    """Serializador para crear/leer `PriceAlert`.

    En creación delega en `alerts.services.crear_alerta`, la misma
    lógica de negocio que usa el formulario web, para evitar duplicar
    reglas entre la API REST y el frontend.
    """

    card = CardSerializer(read_only=True)
    pokemontcg_id = serializers.CharField(write_only=True)
    discount_percentage = serializers.IntegerField(write_only=True, min_value=1, max_value=99)

    class Meta:
        """Meta para `PriceAlertSerializer` que define campos y lecturas."""

        model = PriceAlert
        fields = [
            "id",
            "user",
            "card",
            "pokemontcg_id",
            "discount_percentage",
            "target_price",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["user", "target_price", "is_active"]

    def _obtener_precio_actual(self, pokemontcg_id: str) -> float:
        """Obtiene el precio de mercado ACTUAL de la carta consultando la API.

        No usa el precio guardado en la DB local aunque exista: `Card.price`
        solo se refresca cuando corre `check_pokemon_prices` (hasta 24h de
        antigüedad en producción), y una alerta de precio debe calcularse
        sobre el precio real del mercado en el momento de crearla, no sobre
        un dato potencialmente desactualizado.

        De paso, actualiza `Card.price` con el valor fresco obtenido, para
        que la carta quede al día sin esperar al próximo ciclo del cron.
        """
        card_data = fetch_card(pokemontcg_id)
        if not card_data:
            raise serializers.ValidationError(
                {"pokemontcg_id": "No se pudo obtener la carta de la API."}
            )

        precio = extract_market_price(
            card_data.get("tcgplayer", {}).get("prices", {})
        ) or card_data.get("price")

        if not precio:
            raise serializers.ValidationError(
                {"pokemontcg_id": "Esta carta no tiene precio de mercado disponible."}
            )

        precio = float(precio)

        # Refresca Card.price si la carta ya existe localmente, para no
        # dejarla desactualizada hasta el próximo ciclo del cron.
        Card.objects.filter(pokemontcg_id=pokemontcg_id).update(price=precio)

        return precio

    def create(self, validated_data):
        """Crea una `PriceAlert` delegando en el servicio central
        `crear_alerta`."""
        pokemontcg_id = validated_data.pop("pokemontcg_id")
        discount_percentage = validated_data.pop("discount_percentage")
        user = self.context["request"].user

        current_price = self._obtener_precio_actual(pokemontcg_id)

        try:
            return crear_alerta(
                user=user,
                pokemontcg_id=pokemontcg_id,
                discount_percentage=str(discount_percentage),
                current_price_str=str(current_price),
            )
        except (AlertaSinPrecioValidoError, CartaNoEncontradaError) as e:
            raise serializers.ValidationError({"pokemontcg_id": str(e)})
        except IntegrityError:
            raise serializers.ValidationError(
                {"pokemontcg_id": "Ya tienes una alerta para esta carta."}
            )
