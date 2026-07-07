"""Utilidades de precios para cartas Pokémon TCG.

Contiene helpers reutilizables para extraer valores de mercado desde las
variantes de precios devueltas por la API de TCGPlayer."""


def extract_market_price(prices: dict):
    """Extrae el precio `market` de un diccionario de variantes TCGPlayer.

    Intenta variantes comunes y devuelve el primer `market` válido como `float`.
    Retorna `None` si no hay datos válidos."""
    if not prices:
        return None

    for key in ("holofoil", "normal", "reverseHolofoil"):
        if key in prices:
            market = prices[key].get("market")
            if market:
                return float(market)

    return None
