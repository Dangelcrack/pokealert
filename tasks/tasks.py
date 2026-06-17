import requests
from celery import shared_task
from django.core.mail import send_mail
from cards.models import Card
from alerts.models import PriceAlert, PriceHistory

TCG_API_URL = "https://api.pokemontcg.io/v2/cards/"

@shared_task
def check_pokemon_prices():
    # Obtenemos todas las cartas que tienen alertas activas
    active_cards = Card.objects.filter(alerts__is_active=True).distinct()
    
    for card in active_cards:
        # Consultamos la API externa
        response = requests.get(f"{TCG_API_URL}{card.pokemontcg_id}")
        
        if response.status_code == 200:
            data = response.json().get('data', {})
            # Buscamos el precio promedio en el mercado (Tcgplayer como ejemplo)
            tcgplayer_data = data.get('tcgplayer', {}).get('prices', {})
            
            # Usamos el precio de mercado 'holofoil' o 'normal' dependiendo de lo que exista
            market_price = None
            if 'holofoil' in tcgplayer_data:
                market_price = tcgplayer_data['holofoil'].get('market')
            elif 'normal' in tcgplayer_data:
                market_price = tcgplayer_data['normal'].get('market')
                
            if market_price:
                # 1. Guardamos el historial de precios
                PriceHistory.objects.create(
                    card=card,
                    price=market_price,
                    source='tcgplayer'
                )
                
                # 2. Verificamos las alertas
                alerts = PriceAlert.objects.filter(card=card, is_active=True)
                for alert in alerts:
                    if market_price <= alert.target_price:
                        # 3. Enviamos el correo si el precio bajó
                        send_mail(
                            subject=f'¡Alerta de Precio! {card.name}',
                            message=f'El precio de {card.name} ha bajado a ${market_price}. ¡Es tu momento de comprar!',
                            from_email='pokealert@example.com',
                            recipient_list=[alert.user.email],
                            fail_silently=False,
                        )
                        # Desactivamos la alerta para no hacer spam
                        alert.is_active = False
                        alert.save()