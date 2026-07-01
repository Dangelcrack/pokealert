import requests
import os
import logging
from celery import shared_task
from django.utils import timezone
from django.db import IntegrityError
from datetime import timedelta
from cards.models import Card
from alerts.models import PriceHistory

logger = logging.getLogger(__name__)


@shared_task
def save_daily_prices():
    """Guardar precios de cartas con alertas activas (optimizado)"""

    try:
        # 1. Obtener solo cartas con alertas ACTIVAS
        cards_with_alerts = Card.objects.filter(alerts__is_active=True).distinct()

        if not cards_with_alerts.exists():
            logger.info("⚠️ No hay cartas con alertas activas")
            return "Sin cartas con alertas"

        TCG_API_URL = "https://api.pokemontcg.io/v2/cards"
        api_key = os.getenv("POKEMON_TCG_API_KEY")
        headers = {"X-Api-Key": api_key} if api_key else {}

        # 2. Variables de control
        saved_count = 0
        error_count = 0
        prices_to_create = []

        # 3. Iterar y recolectar (sin insertar aún)
        for card in cards_with_alerts:
            try:
                response = requests.get(
                    f"{TCG_API_URL}/{card.pokemontcg_id}", headers=headers, timeout=5
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    prices_data = data.get("tcgplayer", {}).get("prices", {})
                    price = (
                        prices_data.get("holofoil", {}).get("market")
                        or prices_data.get("reverseHolofoil", {}).get("market")
                        or prices_data.get("normal", {}).get("market")
                    )

                    if price:
                        # 4. Recolectar para batch insert (más rápido)
                        prices_to_create.append(
                            PriceHistory(
                                card=card, price=price, marketplace="tcgplayer"
                            )
                        )
                        saved_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"⚠️ {card.name}: Sin precio holofoil")

            except requests.exceptions.Timeout:
                error_count += 1
                logger.error(f"❌ Timeout en {card.name}")
            except requests.exceptions.RequestException as e:
                error_count += 1
                logger.error(f"❌ Error API en {card.name}: {e}")
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error inesperado en {card.name}: {e}")

        # 5. Insertar TODOS a la vez (bulk insert = mucho más rápido)
        if prices_to_create:
            try:
                PriceHistory.objects.bulk_create(
                    prices_to_create,
                    ignore_conflicts=True,  # Si hay duplicado el mismo día, lo ignora
                )
            except Exception as e:
                logger.error(f"❌ Error en bulk_create: {e}")
                # Fallback: insertar uno por uno
                for price_obj in prices_to_create:
                    try:
                        price_obj.save()
                    except IntegrityError:
                        pass  # Ignorar duplicados

        # 6. Limpiar histórico > 90 días
        deleted_count, _ = PriceHistory.objects.filter(
            recorded_at__lt=timezone.now() - timedelta(days=90)
        ).delete()

        # 7. Log final
        result = f"✅ Guardados: {saved_count} | Errores: {error_count} | Eliminados: {deleted_count}"
        logger.info(result)
        return result

    except Exception as e:
        error_msg = f"❌ Error crítico: {e}"
        logger.error(error_msg)
        return error_msg
