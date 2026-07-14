"""Servicio de obtención de detalle de carta.

Implementa la estrategia de tres capas (Caché -> DB Local -> API/JSON
Externo) y garantiza el registro histórico diario de precio bajo
demanda.
"""

import logging
from django.core.cache import cache
from django.utils import timezone
from django.db import IntegrityError
from alerts.models import PriceHistory
from cards.models import Card
from cards.services.card_formatter import format_card
from cards.services.card_service import get_local_card_by_id, resolve_card_relations
from cards.services.pokemontcg_service import fetch_card

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 horas


def _cache_key(card_id: str) -> str:
    """Genera la clave de caché para el detalle de una carta."""
    return f"card_detail_{card_id}"


def _asegurar_historial_hoy(card_obj, precio: float) -> None:
    if not card_obj or precio <= 0:
        return

    hoy = timezone.now().date()

    try:
        # get_or_create es atómico a nivel de aplicación,
        # pero la restricción UNIQUE en DB es la última barrera.
        obj, created = PriceHistory.objects.get_or_create(
            card=card_obj, date=hoy, defaults={"price": precio, "marketplace": "tcgplayer"}
        )
        if created:
            logger.info(f"[📉 CHART UPDATE] Creado: {card_obj.pokemontcg_id}")
    except IntegrityError:
        # Si la base de datos lanza un IntegrityError, el registro ya existe
        # (o está en medio de una transacción fallida).
        logger.warning(f"[📉 CHART UPDATE] El registro ya existe para {card_obj.pokemontcg_id}")


def obtener_contexto_card_detail(card_id: str) -> dict:
    """Construye el contexto completo para la plantilla `card_detail.html`.

    Aplica la estrategia de tres capas: Caché -> DB Local -> API/JSON Externo.
    Garantiza el registro histórico diario bajo demanda para poblar el
    gráfico de precios. Devuelve un dict con `card`, `market_price` y `error`.
    """
    if not card_id:
        return {"card": {}, "market_price": "N/A", "error": "Identificador de carta no válido."}

    # 1. Estrategia de Caché Dinámica
    cache_key = _cache_key(card_id)
    cached_context = cache.get(cache_key)
    if cached_context:
        logger.info(f"[CACHE HIT] Sirviendo detalles para la carta: {card_id}")
        try:
            card_obj = Card.objects.filter(pokemontcg_id=card_id).first()
            try:
                price_from_cache = float(cached_context.get("market_price") or 0)
            except Exception:
                price_from_cache = 0.0

            if card_obj and price_from_cache > 0:
                hoy = timezone.now().date()
                if not PriceHistory.objects.filter(card=card_obj, recorded_at__date=hoy).exists():
                    PriceHistory.objects.create(
                        card=card_obj,
                        price=price_from_cache,
                        marketplace="tcgplayer",
                    )
                    try:
                        cache.delete(cache_key)
                    except Exception:
                        pass
                    logger.info(
                        f"[CACHE FIX] Creado PriceHistory desde caché para {card_id}: ${price_from_cache}"
                    )
        except Exception as e:
            logger.warning(f"[CACHE FIX] No se pudo asegurar PriceHistory desde caché: {e}")

        return cached_context

    error = None
    card_data_payload = {}
    market_price = "0.00"
    final_parsed_price = 0.0

    # 2. Consulta en Base de Datos Local con Carga Optimizada
    card_obj = (
        Card.objects.select_related("rarity", "supertype", "subtype", "artist", "pokemon_especie")
        .filter(pokemontcg_id=card_id)
        .first()
    )

    is_local_data_valid = False
    if card_obj:
        has_image = bool(card_obj.image_url)
        has_valid_set = card_obj.set_name and card_obj.set_name.lower() != "desconocido"
        has_price_registered = card_obj.price is not None and float(card_obj.price) > 0

        if has_image and has_valid_set and has_price_registered:
            is_local_data_valid = True

    if card_obj and is_local_data_valid:
        logger.info(f"[DATABASE HIT] Registro íntegro para {card_id}. Evitando tráfico de red.")
        final_parsed_price = float(card_obj.price or 0)
        card_data_payload = {
            "id": card_obj.pokemontcg_id,
            "name": card_obj.name,
            "images": {"small": card_obj.image_url, "large": card_obj.image_url},
            "price": final_parsed_price,
            "rarity": card_obj.rarity.display_name if card_obj.rarity else "N/A",
            "artist": card_obj.artist.name if card_obj.artist else "Desconocido",
            "supertype": card_obj.supertype.display_name if card_obj.supertype else "N/A",
            "subtype": card_obj.subtype.display_name if card_obj.subtype else "N/A",
            "pokemon": card_obj.pokemon_especie.name_en if card_obj.pokemon_especie else None,
            "set": {"name": card_obj.set_name},
            "number": card_obj.number,
        }
        market_price = f"{final_parsed_price:.2f}"

    else:
        # 3. Datos locales inexistentes o deficientes: Pipeline de sincronización externa
        if card_obj:
            logger.warning(
                f"[DATA CORRUPTION] Datos insuficientes en DB para {card_id}. Forzando actualización externa."
            )
        else:
            logger.info(f"[DATABASE MISS] Carta {card_id} ausente localmente.")

        api_response_source = get_local_card_by_id(card_id)

        if api_response_source and (
            not api_response_source.get("image_url") and not api_response_source.get("images")
        ):
            logger.warning(
                f"[JSON CORRUPT] El JSON estático carece de recursos multimedia para {card_id}. Escalando a API."
            )
            api_response_source = None

        if api_response_source:
            logger.info(
                f"[STATIC JSON HIT] Datos base recuperados del repositorio estático para {card_id}."
            )
        else:
            logger.info(f"[API HIT] Consultando endpoints oficiales de Pokémon TCG para: {card_id}")
            try:
                api_response_source = fetch_card(card_id)
            except Exception as exc:
                error = f"Excepción crítica al consultar la API externa: {str(exc)}"
                logger.error(error, exc_info=True)
                api_response_source = None

        relations = {}
        if api_response_source and not error:
            relations = resolve_card_relations(api_response_source)
            card_data_payload = format_card(api_response_source)
            card_data_payload["id"] = card_id

            extracted_price = card_data_payload.get("price") or api_response_source.get("price")

            if (
                not extracted_price
                and "tcgplayer" in api_response_source
                and "prices" in api_response_source["tcgplayer"]
            ):
                tcg_market_prices = api_response_source["tcgplayer"]["prices"]
                print_variants = [
                    "holofoil",
                    "reverseHolofoil",
                    "normal",
                    "1stEditionHolofoil",
                    "unlimitedHolofoil",
                ]
                for variant in print_variants:
                    if variant in tcg_market_prices and tcg_market_prices[variant]:
                        extracted_price = tcg_market_prices[variant].get(
                            "market"
                        ) or tcg_market_prices[variant].get("mid")
                        if extracted_price:
                            break

            try:
                final_parsed_price = float(extracted_price) if extracted_price else 0.0
            except (ValueError, TypeError):
                final_parsed_price = 0.0

            card_data_payload["price"] = final_parsed_price
            market_price = f"{final_parsed_price:.2f}"

            if relations.get("rarity"):
                card_data_payload["rarity"] = getattr(relations["rarity"], "display_name", "N/A")
            if relations.get("artist"):
                card_data_payload["artist"] = getattr(relations["artist"], "name", "Desconocido")
            if relations.get("supertype"):
                card_data_payload["supertype"] = getattr(
                    relations["supertype"], "display_name", "N/A"
                )
            if relations.get("subtype"):
                card_data_payload["subtype"] = getattr(relations["subtype"], "display_name", "N/A")
            if relations.get("pokemon_especie"):
                card_data_payload["pokemon"] = getattr(
                    relations["pokemon_especie"], "name_en", None
                )

            inferred_set_name = None
            if "set" in api_response_source and isinstance(api_response_source["set"], dict):
                inferred_set_name = api_response_source["set"].get("name")

            resolved_set_name = (
                card_data_payload.get("set_name")
                or card_data_payload.get("set", {}).get("name")
                or inferred_set_name
                or api_response_source.get("set_name")
                or "Desconocido"
            )
            card_data_payload["set"] = {"name": resolved_set_name}
            card_data_payload["set_name"] = resolved_set_name

            fallback_small = card_data_payload.get("image_url") or api_response_source.get(
                "images", {}
            ).get("small")
            fallback_large = card_data_payload.get("image_url") or api_response_source.get(
                "images", {}
            ).get("large")

            if "images" not in card_data_payload or not card_data_payload["images"]:
                card_data_payload["images"] = {"small": fallback_small, "large": fallback_large}
            else:
                if not card_data_payload["images"].get("small"):
                    card_data_payload["images"]["small"] = fallback_small
                if not card_data_payload["images"].get("large"):
                    card_data_payload["images"]["large"] = fallback_large

            # 4. Persistencia Atómica y Reparación del Registro Local
            card_obj, _ = Card.objects.update_or_create(
                pokemontcg_id=card_id,
                defaults={
                    "name": card_data_payload["name"],
                    "image_url": card_data_payload["images"]["small"],
                    "set_name": card_data_payload["set"]["name"],
                    "number": card_data_payload.get("number"),
                    "price": final_parsed_price if final_parsed_price > 0 else None,
                    **relations,
                },
            )
            logger.info(f"[DB SYNCHRONIZED] Sincronización exitosa para {card_id}.")

        elif not api_response_source and not error:
            error = (
                "La carta solicitada no pudo ser localizada en los repositorios locales ni remotos."
            )

    _asegurar_historial_hoy(card_obj if not error else None, final_parsed_price)

    context = {"card": card_data_payload, "market_price": market_price, "error": error}

    if not error and card_data_payload:
        cache.set(cache_key, context, CACHE_TTL_SECONDS)

    return context
