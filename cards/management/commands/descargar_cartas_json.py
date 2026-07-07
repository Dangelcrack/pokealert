"""Comando de gestión para descargar cartas desde PokéTCG y generar un JSON local.

El JSON generado es compatible con la lógica de búsqueda y normalización de
`cards/views.py` y sirve como respaldo local si la API no está disponible."""

import os
import json
import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    """Comando que descarga cartas desde la API y genera un JSON local.

    Genera un archivo `todas_las_cartas_tcg.json` con información simplificada
    pensada para búsquedas locales y como respaldo cuando la API no esté disponible."""

    help = "Descarga cartas de la API y genera el JSON con textos planos para views.py"

    def handle(self, *args, **options):
        """Ejecuta la descarga y escritura del JSON local.

        Maneja errores de conexión y muestra progreso por stdout."""
        self.stdout.write("Iniciando descarga de cartas...")

        # Traemos un buen lote de cartas para tu buscador
        url = "https://api.pokemontcg.io/v2/cards?pageSize=250"
        headers = {}

        api_key = os.environ.get("POKEMON_TCG_API_KEY")
        if api_key:
            headers["X-Api-Key"] = api_key

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            raw_data = response.json().get("data", [])

            cartas_mapeadas = {}
            for card in raw_data:
                nombre_key = card.get("name", "").lower()

                # La API da los subtipos en una lista ['Stage 2'], sacamos el primero
                subtypes_list = card.get("subtypes", [])
                subtype_str = subtypes_list[0] if subtypes_list else "Unknown"

                # Guardamos TODO en formato de texto plano para que normalize() funcione
                cartas_mapeadas[nombre_key] = {
                    "pokemontcg_id": card.get("id"),
                    "name": card.get("name"),
                    "image_url": card.get("images", {}).get("small", ""),
                    "set_name": card.get("set", {}).get("name", "Unknown"),
                    "number": card.get("number"),
                    "price": card.get("tcgplayer", {})
                    .get("prices", {})
                    .get("holofoil", {})
                    .get("market", None),
                    "hp": card.get("hp"),
                    "types": card.get("types"),
                    # Volvemos a los strings puros que tu views.py adora:
                    "rarity": card.get("rarity", "Unknown"),
                    "supertype": card.get("supertype", "Unknown"),
                    "subtype": subtype_str,
                    "artist": card.get("artist", "Unknown"),
                }

            # Guardamos el archivo sobreescribiendo el anterior
            json_path = os.path.join(settings.BASE_DIR, "todas_las_cartas_tcg.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(cartas_mapeadas, f, ensure_ascii=False, indent=4)

            self.stdout.write(
                self.style.SUCCESS(f"¡Éxito! Archivo JSON corregido y generado en {json_path}.")
            )

        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Error al conectar con la API: {e}"))
