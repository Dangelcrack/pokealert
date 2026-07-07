"""Normaliza y transforma la respuesta de la API Pokémon TCG al formato interno de la aplicación."""

from cards.services.pricing import extract_market_price


def format_card(card_data: dict) -> dict:
    """Normaliza datos de la API de Pokémon TCG a un formato único interno.
    Garantiza compatibilidad absoluta con plantillas que usen card.id o card.pokemontcg_id."""
    if not card_data:
        return {}

    prices = card_data.get("tcgplayer", {}).get("prices", {})
    price = extract_market_price(prices) or card_data.get("price") or 0.0

    set_info = card_data.get("set", {}) or {}

    # Resolución inteligente para evitar IDs numéricos de la base de datos local
    raw_id = card_data.get("id")
    if isinstance(raw_id, int):
        card_identifier = card_data.get("pokemontcg_id") or card_data.get("card_id") or str(raw_id)
    else:
        card_identifier = raw_id or card_data.get("pokemontcg_id") or card_data.get("card_id")

    return {
        "id": card_identifier,
        "pokemontcg_id": card_identifier,
        "name": card_data.get("name", "Desconocido"),
        "image_url": card_data.get("images", {}).get("small", "") or card_data.get("image_url", ""),
        "images": card_data.get("images", {}),
        "price": float(price),
        "rarity": card_data.get("rarity", "N/A"),
        "set_name": (
            set_info.get("name", "Unknown")
            if isinstance(set_info, dict)
            else card_data.get("set_name", "Unknown")
        ),
        "artist": card_data.get("artist", "Desconocido"),
        "supertype": card_data.get("supertype", "N/A"),
        "subtype": (
            card_data.get("subtypes", ["N/A"])[0]
            if isinstance(card_data.get("subtypes"), list) and card_data.get("subtypes")
            else "N/A"
        ),
        "number": card_data.get("number", "N/A"),
        "hp": card_data.get("hp", "N/A"),
        "types": card_data.get("types", []),
    }
