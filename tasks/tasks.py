"""Tareas periódicas del sistema.

Incluye actualización de históricos de precio y sincronización de especies
Pokémon para el modelo `PokemonEspecie`."""

import os
import logging
import requests
from datetime import timedelta
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError
from django.core.cache import cache

from cards.models import Card, PokemonEspecie
from cards.views import extract_market_price
from alerts.models import PriceAlert, PriceHistory

logger = logging.getLogger(__name__)

TCG_API_URL = "https://api.pokemontcg.io/v2/cards"


@shared_task
def check_pokemon_prices():
    """Escanea cartas del sistema, actualiza sus precios de mercado en el histórico
    y evalúa las alertas activas disparando correos si se cumple la condición."""
    try:
        # Modificación: Buscamos todas las cartas que requieran seguimiento histórico (con o sin alertas activas)
        # para evitar congelar el gráfico una vez que la alerta del usuario se desactive.
        tracked_cards = Card.objects.all()

        if not tracked_cards.exists():
            logger.info("⚠️ No hay cartas registradas en el sistema.")
            return "Sin cartas para procesar"

        api_key = os.getenv("POKEMON_TCG_API_KEY") or getattr(settings, "POKEMON_TCG_API_KEY", "")
        headers = {"X-Api-Key": api_key} if api_key else {}

        saved_count = 0
        error_count = 0
        prices_to_create = []
        updated_prices_map = {}

        # 1. Recolectar precios actualizados
        for card in tracked_cards:
            try:
                response = requests.get(
                    f"{TCG_API_URL}/{card.pokemontcg_id}", headers=headers, timeout=5
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    tcgplayer_data = data.get("tcgplayer", {}).get("prices", {})

                    market_price = extract_market_price(tcgplayer_data)

                    if market_price:
                        market_price_float = float(market_price)
                        updated_prices_map[card.pokemontcg_id] = market_price_float

                        # Actualizar precio base en la carta
                        card.price = market_price_float
                        card.save(update_fields=["price"])
                        try:
                            cache.delete(f"card_detail_{card.pokemontcg_id}")
                        except Exception:
                            pass

                        # Evitar duplicados del mismo día en la ejecución de la tarea
                        hoy = timezone.now().date()
                        if not PriceHistory.objects.filter(
                            card=card, recorded_at__date=hoy
                        ).exists():
                            prices_to_create.append(
                                PriceHistory(
                                    card=card, price=market_price_float, marketplace="tcgplayer"
                                )
                            )
                        saved_count += 1
                    else:
                        error_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error procesando {card.name}: {e}")

        # 2. Inserción masiva de históricos
        if prices_to_create:
            try:
                PriceHistory.objects.bulk_create(prices_to_create, ignore_conflicts=True)
            except Exception as e:
                logger.error(f"❌ Error en bulk_create: {e}. Reintentando individualmente...")
                for price_obj in prices_to_create:
                    try:
                        price_obj.save()
                    except IntegrityError:
                        pass

        # 3. Evaluar y disparar correos electrónicos para alertas ACTIVAS
        active_alerts = PriceAlert.objects.filter(is_active=True).select_related("card", "user")
        for alert in active_alerts:
            card = alert.card
            if card.pokemontcg_id in updated_prices_map:
                live_price = updated_prices_map[card.pokemontcg_id]

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
                    send_mail(
                        subject=f"¡Alerta de Precio! {card.name}",
                        message=(
                            f"¡Buenas noticias! El precio de {card.name} ha alcanzado tu objetivo.\n\n"
                            f"Precio objetivo: {target_display}\n"
                            f"Precio actual de mercado: ${live_price:.2f}\n\n"
                            f"¡Es el momento ideal para comprar!"
                        ),
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "pokealert@example.com"),
                        recipient_list=[alert.user.email],
                        fail_silently=False,
                    )
                    alert.is_active = False
                    alert.save(update_fields=["is_active"])

        # 4. Limpieza automática de datos históricos obsoletos (> 90 días)
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
    """Sincroniza el listado básico de especies desde PokéAPI mapeando
    directamente a tu modelo real PokemonEspecie."""
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
                    defaults={"name_en": nombre_api, "name_es": "", "image": url_imagen},
                )
                if created:
                    nuevos_count += 1

            return f"Sincronización de Pokédex completada. Se añadieron {nuevos_count} especies."
        else:
            return f"Error de respuesta PokéAPI: Código {response.status_code}"

    except Exception as e:
        return f"Error fatal en la automatización de la Pokédex: {str(e)}"
