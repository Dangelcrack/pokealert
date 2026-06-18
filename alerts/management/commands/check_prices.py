import os

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from alerts.models import PriceAlert
import requests

class Command(BaseCommand):
    help = "Verifica los precios y envía correos si bajan"

    def handle(self, *args, **options):
        # 1. Ver cuántas alertas hay activas
        alerts = PriceAlert.objects.filter(is_active=True)
        self.stdout.write(f"🔍 Buscando alertas activas en la Base de Datos...")
        self.stdout.write(f"📊 Alertas activas encontradas: {alerts.count()}")

        for alert in alerts:
            self.stdout.write(f"🃏 Comprobando la carta: {alert.card.name} ({alert.card.pokemontcg_id})")
            
            url = f"https://api.pokemontcg.io/v2/cards/{alert.card.pokemontcg_id}"
            api_key = os.getenv('POKEMON_TCG_API_KEY')
            headers = {'X-Api-Key': api_key}
            try:
                response = requests.get(url, headers=headers, timeout=10)
                api_data = response.json().get('data', {})
                
                prices = api_data.get('tcgplayer', {}).get('prices', {})
                current_price = float(prices.get('holofoil', {}).get('market', 0))
                
                # 2. Imprimir los precios que está comparando
                self.stdout.write(f"   -> Precio actual en la API: ${current_price}")
                self.stdout.write(f"   -> Tu precio objetivo: ${alert.target_price}")
                
                if current_price > 0 and current_price <= float(alert.target_price):
                    if alert.user.email:
                        self.stdout.write(f"🚀 ¡OFERTA DETECTADA! Intentando enviar correo real...")
                        
                        send_mail(
                            subject=f"¡Alerta de Precio! 🔥 {alert.card.name} ha bajado",
                            message=f"Hola {alert.user.username}, {alert.card.name} está a ${current_price}",
                            from_email=None,
                            recipient_list=[alert.user.email],
                            fail_silently=False,
                        )
                        
                        self.stdout.write(f"✅ ¡Correo enviado con éxito a {alert.user.email}!")
                        alert.is_active = False
                        alert.save()
                else:
                    # 3. Si no cumple la condición, avisar por qué
                    self.stdout.write("❌ El precio del mercado sigue siendo superior a tu objetivo. No se envía correo.")
                        
            except Exception as e:
                self.stdout.write(f"💥 Error grave procesando la carta: {e}")