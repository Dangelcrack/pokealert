"""Serializadores de API para la aplicación `cards`.

Define cómo se serializan los campos de `Card` para los endpoints REST."""

from rest_framework import serializers
from .models import Card


class CardSerializer(serializers.ModelSerializer):
    """Serializador para el modelo `Card`.

    Normaliza la salida de campos usados por los endpoints REST y por el
    frontend (incluye `id`, `pokemontcg_id`, `name`, `image_url`, etc.)."""

    class Meta:
        """Meta para `CardSerializer` que lista los campos expuestos."""

        model = Card
        fields = ["id", "pokemontcg_id", "name", "image_url", "rarity", "created_at"]
