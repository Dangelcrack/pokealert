POKEMON_ES_TO_TCG = {
    "colmilargo": "Great Tusk",
    "colagrito": "Scream Tail",
    "furioseta": "Brute Bonnet",
    "melenaleteo": "Flutter Mane",
    "reptalada": "Slither Wing",
    "pelarena": "Sandy Shocks",
    "bramaluna": "Roaring Moon",
    "ondulagua": "Walking Wake",

    "ferrodada": "Iron Treads",
    "ferrosaco": "Iron Bundle",
    "ferropalmas": "Iron Hands",
    "ferrocuello": "Iron Jugulis",
    "ferropolilla": "Iron Moth",
    "ferropúas": "Iron Thorns",
    "ferropaladín": "Iron Valiant",
    "ferroverdor": "Iron Leaves",
    "ferromole": "Iron Boulder",
    "ferrotesta": "Iron Crown",
}

TCG_TERMS = {
        # Tipos de carta
        "energia": "energy", "energía": "energy",
        "entrenador": "trainer", "objeto": "item",
        "partidario": "supporter", "estadio": "stadium",
        "herramienta": "tool", "pocion": "potion", "poción": "potion",
        "pokeball": "poke ball", "pokéball": "poke ball",
        
        # Mecánicas y rarezas (¡Crucial para el orden!)
        "radiante": "radiant",
        "brillante": "shining",
        "dorada": "gold",
        "dorado": "gold",
        "arcoiris": "rainbow",
        "arco iris": "rainbow",
    }


import requests
from django.core.cache import cache

# En tu archivo cards/utils.py

def get_filter_options(filter_type): # <--- Asegúrate de que tenga (endpoint) aquí
    """Obtiene datos de la API y los guarda en caché durante 24 horas."""
    cache_key = f"api_options_{filter_type}"
    options = cache.get(cache_key)
    
    if not options:
        try:
            url = f"https://api.pokemontcg.io/v2/{filter_type}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json().get('data', [])
                # Si es una lista de strings simple, sorted(data) está bien.
                # Si son objetos, necesitarás sorted(data, key=lambda x: x)
                options = sorted(data)
                cache.set(cache_key, options, 86400)
        except Exception:
            options = [] 
    return options