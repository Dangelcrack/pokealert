import os
import logging
import requests
from datetime import timedelta
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError

from cards.models import Card, PokemonEspecie
from cards.views import extract_market_price 
from alerts.models import PriceAlert, PriceHistory

logger = logging.getLogger(__name__)

TCG_API_URL = "https://api.pokemontcg.io/v2/cards"


@shared_task
def check_pokemon_prices():
    """
    Escanea cartas con alertas activas, guarda los precios en lote (bulk_create),
    dispara los emails correspondientes y limpia el historial antiguo de 90 días.
    """
    try:
        # 1. Obtener solo cartas con alertas ACTIVAS
        active_cards = Card.objects.filter(alerts__is_active=True).distinct()

        if not active_cards.exists():
            logger.info("⚠️ No hay cartas con alertas activas")
            return "Sin cartas con alertas"

        # Autenticación con la API Key guardada en tus settings/env
        api_key = os.getenv("POKEMON_TCG_API_KEY") or getattr(settings, "POKEMON_TCG_API_KEY", "")
        headers = {"X-Api-Key": api_key} if api_key else {}

        saved_count = 0
        error_count = 0
        prices_to_create = []
        updated_prices_map = {}

        # 2. Iterar sobre las cartas y recolectar precios desde la API externa
        for card in active_cards:
            try:
                response = requests.get(
                    f"{TCG_API_URL}/{card.pokemontcg_id}", headers=headers, timeout=5
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    tcgplayer_data = data.get("tcgplayer", {}).get("prices", {})

                    # Extractor optimizado (holofoil, reverseHolofoil o normal)
                    market_price = extract_market_price(tcgplayer_data)

                    if market_price:
                        market_price_float = float(market_price)
                        updated_prices_map[card.pokemontcg_id] = market_price_float

                        # Actualizar el precio espejo en la tabla local de cartas
                        card.price = market_price_float
                        card.save(update_fields=['price'])

                        # Preparar el objeto para la inserción masiva
                        prices_to_create.append(
                            PriceHistory(
                                card=card, 
                                price=market_price_float, 
                                marketplace="tcgplayer"
                            )
                        )
                        saved_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"⚠️ {card.name}: No se pudo extraer un precio válido")
                else:
                    error_count += 1
                    logger.error(f"❌ Error API en {card.name}: Código {response.status_code}")

            except requests.exceptions.Timeout:
                error_count += 1
                logger.error(f"❌ Timeout en {card.name}")
            except requests.exceptions.RequestException as e:
                error_count += 1
                logger.error(f"❌ Error de red en {card.name}: {e}")
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error inesperado procesando {card.name}: {e}")

        # 3. Insertar TODOS los precios históricos a la vez (Optimización Bulk de tu código original)
        if prices_to_create:
            try:
                PriceHistory.objects.bulk_create(prices_to_create, ignore_conflicts=True)
            except Exception as e:
                logger.error(f"❌ Error en bulk_create: {e}. Aplicando Fallback individual...")
                for price_obj in prices_to_create:
                    try:
                        price_obj.save()
                    except IntegrityError:
                        pass

        # 4. Procesar y disparar las alertas por email basándonos en los precios obtenidos
        for card in active_cards:
            if card.pokemontcg_id in updated_prices_map:
                live_price = updated_prices_map[card.pokemontcg_id]
                alerts = PriceAlert.objects.filter(card=card, is_active=True).select_related('user')
                
                for alert in alerts:
                    if alert.target_price:
                        target = float(alert.target_price)
                        is_triggered = live_price <= target
                        target_display = f"${target:.2f}"
                    else:
                        base_price = float(card.price or 0)
                        target = base_price * (1 - (alert.discount_percentage / 100))
                        is_triggered = live_price <= target
                        target_display = f"${target:.2f} ({alert.discount_percentage}% desc.)"

                    if is_triggered:
                        # Envío del correo al usuario
                        send_mail(
                            subject=f"¡Alerta de Precio! {card.name}",
                            message=(
                                f"¡Buenas noticias! El precio de {card.name} ha alcanzado tu objetivo.\n\n"
                                f"Precio objetivo: {target_display}\n"
                                f"Precio actual de mercado: ${live_price:.2f}\n\n"
                                f"¡Es el momento ideal para comprar!"
                            ),
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'pokealert@example.com'),
                            recipient_list=[alert.user.email],
                            fail_silently=False,
                        )
                        alert.is_active = False
                        alert.save(update_fields=['is_active'])

        # 5. Limpieza automática de datos históricos obsoletos (> 90 días) para cuidar tu SQLite
        deleted_count, _ = PriceHistory.objects.filter(
            recorded_at__lt=timezone.now() - timedelta(days=90)
        ).delete()

        result_summary = f"✅ Completado. Guardados: {saved_count} | Errores: {error_count} | Historial purgado: {deleted_count}"
        logger.info(result_summary)
        return result_summary

    except Exception as e:
        error_msg = f"❌ Error crítico en check_pokemon_prices: {e}"
        logger.error(error_msg)
        return error_msg


@shared_task
def actualizar_pokedex_automatica():
    """
    Sincroniza el listado básico de especies desde PokéAPI mapeando
    directamente a tu modelo real PokemonEspecie.
    """
    url = "https://pokeapi.co/api/v2/pokemon?limit=1500"

    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            resultados = response.json().get("results", [])
            nuevos_count = 0

            for index, p in enumerate(resultados, start=1):
                nombre_api = p["name"].capitalize()
                url_imagen = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{index}.png"

                obj, created = PokemonEspecie.objects.get_or_create(
                    numero_pokedex=index, 
                    defaults={
                        "name_en": nombre_api, 
                        "name_es": "", 
                        "image": url_imagen
                    }
                )
                if created:
                    nuevos_count += 1

            return f"Sincronización de Pokédex completada. Se añadieron {nuevos_count} especies."
        else:
            return f"Error de respuesta PokéAPI: Código {response.status_code}"

    except Exception as e:
        return f"Error fatal en la automatización de la Pokédex: {str(e)}"