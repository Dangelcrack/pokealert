"""Tareas periódicas del sistema optimizadas para bajo consumo de memoria y tiempo.

Incluye actualización de históricos de precio y sincronización de especies
Pokémon para el modelo PokemonEspecie.
"""

import os
import logging
import requests
import time
from datetime import timedelta
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.core.cache import cache

from cards.models import Card, PokemonEspecie
from cards.services.pricing import extract_market_price
from alerts.models import PriceAlert, PriceHistory

logger = logging.getLogger(__name__)

TCG_API_URL = "https://api.pokemontcg.io/v2/cards"


@shared_task
def check_pokemon_prices():
    """Escanea cartas del sistema, actualiza sus precios de mercado en el histórico
    y evalúa las alertas activas disparando correos si se cumple la condición.
    """
    try:
        # 1. Preparar datos iniciales y optimizar queries
        tracked_cards = Card.objects.all()
        if not tracked_cards.exists():
            logger.info("⚠️ No hay cartas registradas en el sistema.")
            return "Sin cartas para procesar"

        api_key = os.getenv("POKEMON_TCG_API_KEY") or getattr(settings, "POKEMON_TCG_API_KEY", "")
        headers = {"X-Api-Key": api_key} if api_key else {}

        hoy = timezone.now().date()

        # Optimización: Mapear cartas que ya tienen histórico hoy para evitar un .exists() por carta
        historicos_hoy = set(
            PriceHistory.objects.filter(recorded_at__date=hoy).values_list("card_id", flat=True)
        )

        saved_count = 0
        error_count = 0
        prices_to_create = []
        cards_to_update = []
        updated_prices_map = {}

        # Reutilización de conexiones HTTP mediante requests.Session
        session = requests.Session()
        session.headers.update(headers)

        # Convertimos el QuerySet a una lista de IDs y mapeamos las cartas en memoria
        card_ids = list(tracked_cards.values_list("pokemontcg_id", flat=True))
        cards_dict = {c.pokemontcg_id: c for c in tracked_cards}

        # Procesaremos las cartas agrupadas en bloques para no saturar la API externa
        tamanio_lote = 10

        for i in range(0, len(card_ids), tamanio_lote):
            lote_ids = card_ids[i : i + tamanio_lote]

            # Construimos la query masiva: "id:id1 OR id:id2 OR id:id3..."
            query_string = " OR ".join([f"id:{pid}" for pid in lote_ids])

            try:
                # Solicitamos el lote completo de cartas en una sola llamada HTTP
                response = session.get(
                    TCG_API_URL, params={"q": query_string, "pageSize": tamanio_lote}, timeout=30
                )

                if response.status_code == 200:
                    data_list = response.json().get("data", [])

                    for card_data in data_list:
                        pid = card_data.get("id")
                        card = cards_dict.get(pid)

                        if not card:
                            continue

                        tcgplayer_data = card_data.get("tcgplayer", {}).get("prices", {})
                        market_price = extract_market_price(tcgplayer_data)

                        if market_price:
                            market_price_float = float(market_price)
                            updated_prices_map[pid] = market_price_float

                            # Modificar objeto en memoria
                            card.price = market_price_float
                            cards_to_update.append(card)

                            # Invalidar caché de forma segura
                            try:
                                cache.delete(f"card_detail_{pid}")
                            except Exception:
                                pass

                            # Verificar en el set local (O(1)) si ya se procesó hoy
                            if card.id not in historicos_hoy:
                                prices_to_create.append(
                                    PriceHistory(
                                        card=card, price=market_price_float, marketplace="tcgplayer"
                                    )
                                )
                            saved_count += 1
                        else:
                            error_count += 1
                else:
                    error_count += len(lote_ids)
                    logger.error(
                        f"❌ Error de API de Pokémon. Código de estado: {response.status_code}"
                    )

            except Exception as e:
                error_count += len(lote_ids)
                logger.error(f"❌ Error crítico procesando lote de cartas: {e}")

            # Pausa de 1 segundo entre bloques para cumplir las buenas prácticas de la API
            time.sleep(1.0)

        # 2. Guardado masivo en la Base de Datos (Atomicidad y Eficiencia)
        with transaction.atomic():
            if cards_to_update:
                Card.objects.bulk_update(cards_to_update, fields=["price"], batch_size=100)

            if prices_to_create:
                try:
                    PriceHistory.objects.bulk_create(
                        prices_to_create, ignore_conflicts=True, batch_size=100
                    )
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
                    target_display = f"${target:.2f}"
                else:
                    base_price = float(card.price or 0)
                    target = base_price * (1 - (alert.discount_percentage / 100))
                    target_display = f"${target:.2f} ({alert.discount_percentage}% desc.)"

                if live_price <= target:
                    try:
                        send_mail(
                            subject=f"¡Alerta de Precio! {card.name}",
                            message=(
                                f"¡Buenas noticias! El precio de {card.name} ha alcanzado tu objetivo.\n\n"
                                f"Precio objetivo: {target_display}\n"
                                f"Precio actual de mercado: ${live_price:.2f}\n\n"
                                f"¡Es el momento ideal para comprar!"
                            ),
                            from_email=getattr(
                                settings, "DEFAULT_FROM_EMAIL", "pokealert@example.com"
                            ),
                            recipient_list=[alert.user.email],
                            fail_silently=False,
                        )
                        alert.is_active = False
                        alert.save(update_fields=["is_active"])
                    except Exception as mail_error:
                        logger.error(
                            f"❌ Error enviando email para alerta {alert.id}: {mail_error}"
                        )

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
    directamente a tu modelo real PokemonEspecie.
    """
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
