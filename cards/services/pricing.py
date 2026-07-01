def extract_market_price(prices: dict):
    if not prices:
        return None

    for key in ("holofoil", "normal", "reverseHolofoil"):
        if key in prices:
            market = prices[key].get("market")
            if market:
                return float(market)

    return None