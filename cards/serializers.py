from rest_framework import serializers
from .models import Card


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ["id", "pokemontcg_id", "name", "image_url", "rarity", "created_at"]
