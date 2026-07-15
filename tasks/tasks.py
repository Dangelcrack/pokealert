"""Tareas periódicas del sistema optimizadas para bajo consumo de memoria y
tiempo.

Incluye actualización de históricos de precio y sincronización de
especies Pokémon para el modelo PokemonEspecie.
"""

import logging
import requests
import time
from datetime import timedelta
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from cards.utils import _execute_api_request
from cards.models import Card, PokemonEspecie
from cards.services.pricing import extract_market_price
from alerts.models import PriceAlert, PriceHistory

logger = logging.getLogger(__name__)

TCG_API_URL = "https://api.pokemontcg.io/v2/cards"


@shared_task
def check_pokemon_prices():
    try:
        tracked_cards = Card.objects.all()
        if not tracked_cards.exists():
            return "Sin cartas para procesar"

        hoy = timezone.now().date()
        historicos_hoy = set(
            PriceHistory.objects.filter(recorded_at__date=hoy).values_list("card_id", flat=True)
        )

        saved_count, error_count = 0, 0
        prices_to_create, cards_to_update, updated_prices_map = [], [], {}
        cards_dict = {c.pokemontcg_id: c for c in tracked_cards}
        card_ids = list(cards_dict.keys())
        tamanio_lote = 10

        for i in range(0, len(card_ids), tamanio_lote):
            lote_ids = card_ids[i : i + tamanio_lote]
            query_string = " OR ".join([f"id:{pid}" for pid in lote_ids])

            try:
                # _execute_api_request debe manejar los reintentos (ej: usando urllib3 retries)
                response = _execute_api_request(
                    TCG_API_URL, params={"q": query_string, "pageSize": tamanio_lote}
                )

                # --- FIX: Validación robusta de respuesta ---
                if response is None or response.status_code != 200:
                    logger.warning(
                        f"Error {response.status_code if response else 'No Response'} en lote {lote_ids}"
                    )
                    error_count += len(lote_ids)
                    continue

                if not response.content:
                    logger.warning(f"Respuesta vacía en lote {lote_ids}")
                    continue

                data = response.json().get("data", [])

                for card_data in data:
                    pid = card_data.get("id")
                    card = cards_dict.get(pid)
                    if not card:
                        continue

                    tcgplayer_data = card_data.get("tcgplayer", {}).get("prices", {})
                    market_price = extract_market_price(tcgplayer_data)

                    if market_price:
                        val = float(market_price)
                        updated_prices_map[pid] = val
                        card.price = val
                        cards_to_update.append(card)
                        cache.delete(f"card_detail_{pid}")

                        if card.id not in historicos_hoy:
                            prices_to_create.append(
                                PriceHistory(card=card, price=val, marketplace="tcgplayer")
                            )
                            saved_count += 1

            except ValueError:
                logger.error(
                    f"El servidor devolvió un formato inválido (no JSON) para el lote {lote_ids}"
                )
                error_count += len(lote_ids)
            except Exception as e:
                error_count += len(lote_ids)
                logger.error(f"Error procesando lote {lote_ids}: {e}")

            time.sleep(1.5)  # Pausa estratégica

        # 2. Guardado masivo
        with transaction.atomic():
            if cards_to_update:
                Card.objects.bulk_update(cards_to_update, fields=["price"], batch_size=100)
            if prices_to_create:
                PriceHistory.objects.bulk_create(
                    prices_to_create, ignore_conflicts=True, batch_size=100
                )

        # 3. Alertas
        active_alerts = PriceAlert.objects.filter(is_active=True).select_related("card", "user")
        for alert in active_alerts:
            card = alert.card
            if card.pokemontcg_id in updated_prices_map:
                live_price = updated_prices_map[card.pokemontcg_id]
                target = (
                    float(alert.target_price)
                    if alert.target_price
                    else float(card.price or 0) * (1 - (alert.discount_percentage / 100))
                )

                if live_price <= target:
                    try:
                        send_mail(
                            f"Alerta: {card.name}",
                            f"Precio actual: ${live_price:.2f}",
                            settings.DEFAULT_FROM_EMAIL,
                            [alert.user.email],
                        )
                        alert.is_active = False
                        alert.save(update_fields=["is_active"])
                    except Exception as e:
                        logger.error(f"Error email {alert.id}: {e}")

        # 4. Limpieza
        deleted_count, _ = PriceHistory.objects.filter(
            recorded_at__lt=timezone.now() - timedelta(days=90)
        ).delete()
        return f"✅ Completado. Guardados: {saved_count} | Errores: {error_count} | Historial purgado: {deleted_count}"

    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
        return str(e)


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

            # Agrupar operaciones dentro de una transacción para acelerar la inserción masiva
            with transaction.atomic():
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
