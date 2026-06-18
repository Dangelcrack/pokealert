import os
import requests
from rest_framework import serializers
from .models import PriceAlert, PriceHistory
from cards.models import Card
from cards.serializers import CardSerializer


class PriceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceHistory
        fields = ['id', 'price', 'source', 'recorded_at']


class PriceAlertSerializer(serializers.ModelSerializer):
    card = CardSerializer(read_only=True)
    pokemontcg_id = serializers.CharField(write_only=True)
    discount_percentage = serializers.IntegerField(write_only=True, min_value=1, max_value=99)
    
    class Meta:
        model = PriceAlert
        fields = ['id', 'user', 'card', 'pokemontcg_id', 'discount_percentage', 'target_price', 'is_active', 'created_at']
        read_only_fields = ['user', 'target_price', 'is_active']

    def create(self, validated_data):
        pokemontcg_id = validated_data.pop('pokemontcg_id')
        discount_percentage = validated_data.pop('discount_percentage')
        user = self.context['request'].user

        # 1. Consultar API de Pokémon TCG
        url = f"https://api.pokemontcg.io/v2/cards/{pokemontcg_id}"
        
        try:
            # Leer API Key de forma segura desde .env
            api_key = os.getenv('POKEMON_TCG_API_KEY')
            if not api_key:
                raise serializers.ValidationError({
                    "pokemontcg_id": "Error de configuración: falta la API Key"
                })
            
            headers = {
                "User-Agent": "PokeAlertApp/1.0",
                'X-Api-Key': api_key
            }
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise serializers.ValidationError({
                    "pokemontcg_id": f"La API devolvió código de error: {response.status_code}"
                })
            
            api_data = response.json().get('data', {})
            
        except requests.exceptions.RequestException as e:
            raise serializers.ValidationError({
                "pokemontcg_id": f"Error de conexión con la API: {str(e)}"
            })
        except Exception as e:
            raise serializers.ValidationError({
                "pokemontcg_id": f"Error inesperado: {str(e)}"
            })

        # 2. Extraer precio de mercado
        tcgplayer_prices = api_data.get('tcgplayer', {}).get('prices', {})
        market_price = None
        if 'holofoil' in tcgplayer_prices:
            market_price = tcgplayer_prices['holofoil'].get('market')
        elif 'normal' in tcgplayer_prices:
            market_price = tcgplayer_prices['normal'].get('market')

        if not market_price:
            raise serializers.ValidationError({
                "pokemontcg_id": "Esta carta no tiene precio de mercado disponible."
            })

        # 3. Normalizar rareza
        raw_rarity = api_data.get('rarity', '').lower()
        if 'holo' in raw_rarity:
            db_rarity = 'holorare'
        elif 'rare' in raw_rarity:
            db_rarity = 'rare'
        elif 'uncommon' in raw_rarity:
            db_rarity = 'uncommon'
        else:
            db_rarity = 'common'

        # 4. Crear o obtener carta
        card, created = Card.objects.get_or_create(
            pokemontcg_id=pokemontcg_id,
            defaults={
                'name': api_data.get('name'),
                'image_url': api_data.get('images', {}).get('small', ''),
                'rarity': db_rarity
            }
        )

        # 5. Calcular precio objetivo
        calculated_target = float(market_price) * (1 - (discount_percentage / 100.0))

        # 6. Validar que no exista alerta duplicada
        if PriceAlert.objects.filter(user=user, card=card).exists():
            raise serializers.ValidationError({
                "pokemontcg_id": "Ya tienes una alerta para esta carta."
            })

        # 7. Crear alerta
        price_alert = PriceAlert.objects.create(
            user=user,
            card=card,
            target_price=calculated_target,
            **validated_data
        )

        return price_alert