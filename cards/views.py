"""Vistas y utilidades principales de la aplicación `cards`.

Este módulo combina helpers de búsqueda, normalización, sincronización con la API,
views frontend y endpoints de API REST para cartas y alertas."""

import os
import math
import json
import logging
import unicodedata
from datetime import timedelta

from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.core.cache import cache
from django.db import connection
from django.conf import settings
from django.utils import timezone


from rest_framework import viewsets

from cards.services.pokemontcg_service import fetch_cards, fetch_card
from alerts.models import PriceAlert, PriceHistory
from cards.utils import POKEMON_ES_TO_TCG, TCG_TERMS, get_filter_options as get_api_filter_options
from .models import Card, Rarity, Supertype, Subtype, Artist, PokemonEspecie
from .serializers import CardSerializer

logger = logging.getLogger(__name__)

# ==========================================
# FUNCIONES AUXILIARES Y DE CONFIGURACIÓN
# ==========================================


def warm_up_database():
    """Ejecuta una consulta ligera para inicializar la conexión a la base de datos.

    Uso: llamada esperada al inicio de la aplicación para evitar latencias por
    conexiones perezosas en la primera petición.
    No devuelve valor y silencia cualquier excepción de conexión."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM cards_card")
    except Exception:
        pass


def safe_append(query_parts, model, id_value, label, field):
    """Evita que IDs vacíos o inválidos rompan la construcción de la consulta.

    Parámetros:
    - query_parts: lista que recibe fragmentos de consulta.
    - model: modelo Django usado para validar el id.
    - id_value: valor del id que se quiere resolver.
    - label: etiqueta que se añade a la consulta construida.
    - field: campo del objeto para usar en la etiqueta.

    Comportamiento: si `id_value` no es un entero válido o el objeto no existe,
    la función no modifica `query_parts` y devuelve silenciosamente."""
    if not id_value or not str(id_value).isdigit():
        return
    try:
        obj = model.objects.get(id=id_value)
        query_parts.append(f'{label}:"{getattr(obj, field)}"')
    except (model.DoesNotExist, ValueError, TypeError):
        return


def normalize(text):
    """Normaliza una cadena para comparaciones: devuelve minúsculas sin acentos.

    Retorna una cadena vacía si la entrada es falsy. Utiliza NFD para separar
    diacríticos y filtra los caracteres de marca."""
    if not text:
        return ""
    text = str(text).lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def get_expanded_search_terms(query_raw: str) -> set:
    """Expande un término de búsqueda con sinónimos y traducciones relevantes.

    Devuelve un conjunto de términos en minúsculas que incluye la cadena
    original normalizada y coincidencias encontradas en los mapeos
    `POKEMON_ES_TO_TCG` y `TCG_TERMS`."""
    if not query_raw:
        return set()

    query_norm = normalize(query_raw)
    terms = {query_raw.strip().lower()}

    for es_key, en_value in POKEMON_ES_TO_TCG.items():
        if es_key.startswith(query_norm) or query_norm in es_key:
            terms.add(en_value.lower())

    for es_key, en_value in TCG_TERMS.items():
        if es_key.startswith(query_norm) or query_norm in es_key:
            terms.add(en_value.lower())

    return terms


def build_search_query(
    query_raw: str, rarity=None, supertype=None, subtype=None, artist=None
) -> str:
    """Construye una consulta Lucene para la API externa a partir de filtros.

    Parámetros:
    - query_raw: término de búsqueda ingresado por el usuario.
    - rarity, supertype, subtype, artist: ids de modelos usados como filtros

    Devuelve una cadena con la consulta preparada para enviar a la API."""
    query_parts = []

    if query_raw:
        expanded_terms = get_expanded_search_terms(query_raw)
        name_conditions = []
        for term in expanded_terms:
            if " " in term:
                name_conditions.append(f'name:"{term}"')
            else:
                name_conditions.append(f"name:{term}")

        if name_conditions:
            query_parts.append(f"({' OR '.join(name_conditions)})")

    if rarity:
        safe_append(query_parts, Rarity, rarity, "rarity", "name")
    if supertype:
        safe_append(query_parts, Supertype, supertype, "supertype", "name")
    if subtype:
        safe_append(query_parts, Subtype, subtype, "subtypes", "name")
    if artist:
        safe_append(query_parts, Artist, artist, "artist", "name")

    return " AND ".join(query_parts)


def translate_query(query_raw: str) -> str:
    """Traduce un término de búsqueda desde español a su equivalente TCG (inglés).

    Busca coincidencias en el modelo `PokemonEspecie` y en los diccionarios de
    mapeo del proyecto. Si no encuentra traducción, devuelve el término original
    recortado."""
    if not query_raw:
        return ""
    q = normalize(query_raw)
    pokemon = PokemonEspecie.objects.filter(
        Q(name_es__icontains=q) | Q(name_en__icontains=q)
    ).first()
    if pokemon:
        return pokemon.name_en
    if q in TCG_TERMS:
        return TCG_TERMS[q]
    if q in POKEMON_ES_TO_TCG:
        return POKEMON_ES_TO_TCG[q]
    for es, en in POKEMON_ES_TO_TCG.items():
        if normalize(es).startswith(q):
            return en
    return query_raw.strip()


def invalidate_filter_options_cache():
    """Elimina la entrada en caché que contiene las opciones de filtro.

    Se usa después de crear nuevos registros relacionados con filtros
    para forzar recálculo en la siguiente petición."""
    cache.delete("filter_options_all")


def sync_api_filter_values():
    """Solicita valores de filtros a la API externa y los persiste en la DB local.

    Crea `Supertypes`, `Subtypes` y `Rarities` si no existen para asegurar que
    los menús de filtro muestren todas las opciones disponibles."""
    mapping = [
        (Supertype, "supertypes", "display_name"),
        (Subtype, "subtypes", "display_name"),
        (Rarity, "rarities", "display_name"),
    ]
    for model, filter_type, display_field in mapping:
        options = get_api_filter_options(filter_type)
        for label in options:
            if not label:
                continue
            normalized = normalize(label)
            model.objects.get_or_create(
                name=normalized,
                defaults={display_field: label},
            )


def get_filter_options(filter_name=None):
    """Devuelve las opciones de filtro (cached) para filtros de la interfaz.

    Si la caché está vacía o la base de datos no parece completa, sincroniza
    los valores con la API externa antes de construir el resultado. Si se pasa
    `filter_name`, devuelve solo ese subconjunto."""
    cache_key = "filter_options_all"
    filters = cache.get(cache_key)

    db_complete = (
        Supertype.objects.count() >= 3
        and Subtype.objects.count() >= 20
        and Rarity.objects.count() >= 20
    )

    if filters is None or not db_complete:
        sync_api_filter_values()

        filters = {
            "supertypes": list(Supertype.objects.all().order_by("display_name")),
            "subtypes": list(Subtype.objects.all().order_by("display_name")),
            "rarities": list(Rarity.objects.all().order_by("display_name")),
            "artists": list(Artist.objects.all().order_by("name")),
        }
        cache.set(cache_key, filters, 3600)

    if filter_name:
        return filters.get(filter_name)
    return filters


def get_local_card_by_id(card_id: str):
    """Recupera una carta desde el archivo JSON local `todas_las_cartas_tcg.json`.

    Busca por varios identificadores posibles (`id`, `pokemontcg_id`, `card_id`).
    Devuelve el diccionario de la carta o `None` si no existe o si el archivo
    no puede leerse correctamente."""
    json_path = os.path.join(settings.BASE_DIR, "todas_las_cartas_tcg.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    cards = data.get("data", list(data.values())) if isinstance(data, dict) else data
    for card in cards:
        if str(card.get("id") or card.get("pokemontcg_id") or card.get("card_id")) == str(card_id):
            return card
    return None


def extract_market_price(prices: dict):
    """Extrae el precio de mercado del diccionario `prices` devuelto por TCGPlayer.

    Intenta variantes habituales (`holofoil`, `normal`, `reverseHolofoil`) y
    devuelve el primer `market` válido como `float`. Retorna `None` si no hay
    precio disponible."""
    if not prices:
        return None
    for t in ["holofoil", "normal", "reverseHolofoil"]:
        if t in prices:
            price = prices[t].get("market")
            if price:
                return float(price)
    return None


def format_card(card_data: dict):
    """Normaliza la estructura de una carta para consumo del frontend.

    Devuelve un diccionario con campos estándar (`id`, `name`, `images`,
    `price`, `rarity`, `set_name`, etc.)."""
    if not card_data:
        return {}
    prices = card_data.get("tcgplayer", {}).get("prices", {})
    price = extract_market_price(prices) or 0.0
    return {
        "id": card_data.get("id"),
        "name": card_data.get("name"),
        "image_url": card_data.get("image_url") or card_data.get("images", {}).get("small", ""),
        "images": card_data.get("images", {}),
        "price": price,
        "rarity": card_data.get("rarity", "N/A"),
        "set_name": card_data.get("set_name") or card_data.get("set", {}).get("name", "Unknown"),
        "set": {
            "name": card_data.get("set", {}).get("name", "Desconocido"),
            "series": card_data.get("set", {}).get("series", ""),
        },
        "artist": card_data.get("artist", "Desconocido"),
        "supertype": card_data.get("supertype", "N/A"),
        "subtype": card_data.get("subtypes", ["N/A"])[0] if card_data.get("subtypes") else "N/A",
        "number": card_data.get("number", "N/A"),
        "hp": card_data.get("hp", "N/A"),
        "types": card_data.get("types", []),
    }


def resolve_card_relations(card_data: dict):
    """Resuelve y crea (si procede) las relaciones referenciales para una carta.

    Retorna un dict con instancias para `rarity`, `supertype`, `subtype`,
    `artist` y `pokemon_especie` cuando aplica. Invalida la caché de opciones
    de filtro si se generan nuevos registros."""
    relations = {}
    if card_data.get("rarity"):
        rarity, created = Rarity.objects.get_or_create(
            name=normalize(card_data["rarity"]),
            defaults={"display_name": card_data["rarity"]},
        )
        relations["rarity"] = rarity
        if created:
            invalidate_filter_options_cache()
    if card_data.get("supertype"):
        supertype, created = Supertype.objects.get_or_create(
            name=normalize(card_data["supertype"]),
            defaults={"display_name": card_data["supertype"]},
        )
        relations["supertype"] = supertype
        if created:
            invalidate_filter_options_cache()
    if card_data.get("subtypes") and isinstance(card_data["subtypes"], list):
        subtype_name = card_data["subtypes"][0] if card_data["subtypes"] else None
        if subtype_name:
            subtype, created = Subtype.objects.get_or_create(
                name=normalize(subtype_name), defaults={"display_name": subtype_name}
            )
            relations["subtype"] = subtype
            if created:
                invalidate_filter_options_cache()
    if card_data.get("artist"):
        artist, created = Artist.objects.get_or_create(name=card_data["artist"])
        relations["artist"] = artist
        if created:
            invalidate_filter_options_cache()
    if card_data.get("name"):
        pokemon = PokemonEspecie.objects.filter(
            Q(name_en__icontains=card_data["name"]) | Q(name_es__icontains=card_data["name"])
        ).first()
        if pokemon:
            relations["pokemon_especie"] = pokemon
    return relations


# ==========================================
# VISTAS DE USUARIOS
# ==========================================


class CardViewSet(viewsets.ModelViewSet):
    """API REST para `Card` con operaciones CRUD y campos de búsqueda/filtrado."""

    queryset = Card.objects.all()
    serializer_class = CardSerializer
    search_fields = ["name"]
    filterset_fields = ["rarity", "supertype", "subtype", "artist"]


def home(request):
    """Renderiza la página de inicio del servicio."""
    return render(request, "home.html")


@require_http_methods(["GET", "POST"])
def register(request):
    """Registra un nuevo usuario y realiza login automático.

    Valida que las contraseñas coincidan y que el nombre de usuario no exista."""
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")
        if password != password_confirm:
            return render(request, "auth/register.html", {"error": "Las contraseñas no coinciden"})
        if User.objects.filter(username=username).exists():
            return render(request, "auth/register.html", {"error": "El usuario ya existe"})
        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        return redirect("home")
    return render(request, "auth/register.html")


@require_http_methods(["GET", "POST"])
def user_login(request):
    """Autentica a un usuario con credenciales proporcionadas en el formulario.

    En caso de fallo devuelve la plantilla con un mensaje de error."""
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return redirect("home")
        return render(request, "auth/login.html", {"error": "Usuario o contraseña incorrectos"})
    return render(request, "auth/login.html")


def user_logout(request):
    """Cierra la sesión del usuario y redirige a la página principal."""
    logout(request)
    return redirect("home")


@login_required(login_url="login")
def dashboard(request):
    """Muestra el panel de usuario con las alertas asociadas."""
    alerts = request.user.alerts.all()
    return render(request, "dashboard.html", {"alerts": alerts})


# ==========================================
# VISTAS DE BÚSQUEDA (MÁXIMA PRIORIDAD DB)
# ==========================================


@login_required(login_url="login")
def search(request):
    """Gestión de la búsqueda de cartas combinando DB local, JSON y API externa.

    Soporta filtros por rareza, supertype, subtype y artista, y devuelve la
    plantilla `search.html` con los resultados paginados."""
    query_raw = request.GET.get("q", "").strip()
    selected_sort = request.GET.get("sort", "")
    selected_supertype_id = request.GET.get("supertype", "")
    selected_rarity_id = request.GET.get("rarity", "")
    selected_subtype_id = request.GET.get("subtype", "")
    selected_artist_id = request.GET.get("artist", "")

    page_param = request.GET.get("page")
    current_page = max(1, int(page_param) if page_param and page_param.isdigit() else 1)
    page_size = 24

    # Construir query externa de forma segura
    api_query = build_search_query(
        query_raw,
        selected_rarity_id,
        selected_supertype_id,
        selected_subtype_id,
        selected_artist_id,
    )

    error = None
    results = []
    total_pages = 1

    unique_cards_map = {}
    if (
        query_raw
        or selected_rarity_id
        or selected_supertype_id
        or selected_subtype_id
        or selected_artist_id
    ):
        db_filters = Q()
        if query_raw:
            target_terms = get_expanded_search_terms(query_raw)
            name_q = Q()
            for term in target_terms:
                name_q |= Q(name__icontains=term)
            db_filters &= name_q

        # Validar numéricos para evitar ValueErrors ocultos
        if selected_rarity_id and str(selected_rarity_id).isdigit():
            db_filters &= Q(rarity_id=selected_rarity_id)
        if selected_supertype_id and str(selected_supertype_id).isdigit():
            db_filters &= Q(supertype_id=selected_supertype_id)
        if selected_subtype_id and str(selected_subtype_id).isdigit():
            db_filters &= Q(subtype_id=selected_subtype_id)
        if selected_artist_id and str(selected_artist_id).isdigit():
            db_filters &= Q(artist_id=selected_artist_id)

        db_results = Card.objects.filter(db_filters).select_related(
            "rarity", "supertype", "subtype", "artist"
        )[:150]
        for c in db_results:
            unique_cards_map[c.pokemontcg_id] = {
                "id": c.pokemontcg_id,
                "name": c.name,
                "image_url": c.image_url,
                "images": {"small": c.image_url, "large": c.image_url},
                "price": float(c.price or 0.0),
                "set_name": c.set_name,
                "set": {"name": c.set_name or "Desconocido", "series": ""},
                "number": c.number or "N/A",
                "rarity": c.rarity.display_name if c.rarity else "N/A",
                "supertype": c.supertype.display_name if c.supertype else "N/A",
                "subtypes": [c.subtype.display_name] if c.subtype else ["N/A"],
                "artist": c.artist.name if c.artist else "Desconocido",
            }

    if api_query:
        try:
            api_data = fetch_cards(api_query)
            if api_data:
                for card in api_data:
                    cid = card.get("id")
                    if cid:
                        unique_cards_map[cid] = card
        except Exception as e:
            logger.warning(f"API Externa no disponible o falló temporalmente: {e}")

    json_path = os.path.join(settings.BASE_DIR, "todas_las_cartas_tcg.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data_cargada = json.load(f)
            local_cards = (
                data_cargada.get("data", list(data_cargada.values()))
                if isinstance(data_cargada, dict)
                else data_cargada
            )

            target_terms = get_expanded_search_terms(query_raw) if query_raw else set()
            target_rarity = (
                Rarity.objects.filter(id=selected_rarity_id).first().name
                if selected_rarity_id and str(selected_rarity_id).isdigit()
                else None
            )
            target_supertype = (
                Supertype.objects.filter(id=selected_supertype_id).first().name
                if selected_supertype_id and str(selected_supertype_id).isdigit()
                else None
            )
            target_subtype = (
                Subtype.objects.filter(id=selected_subtype_id).first().name
                if selected_subtype_id and str(selected_subtype_id).isdigit()
                else None
            )
            target_artist = (
                Artist.objects.filter(id=selected_artist_id).first().name
                if selected_artist_id and str(selected_artist_id).isdigit()
                else None
            )

            for card in local_cards:
                match = True
                if target_terms:
                    card_name = card.get("name", "").lower()
                    if not any(term in card_name for term in target_terms):
                        match = False
                if target_rarity and normalize(card.get("rarity")) != normalize(target_rarity):
                    match = False
                if target_supertype and normalize(card.get("supertype")) != normalize(
                    target_supertype
                ):
                    match = False
                if target_artist and normalize(card.get("artist")) != normalize(target_artist):
                    match = False
                if target_subtype:
                    subtypes_list = card.get("subtypes", [])
                    if isinstance(subtypes_list, str):
                        subtypes_list = [subtypes_list]
                    if not any(normalize(st) == normalize(target_subtype) for st in subtypes_list):
                        match = False

                if match:
                    cid = card.get("id") or card.get("pokemontcg_id")
                    if cid and cid not in unique_cards_map:
                        unique_cards_map[cid] = card
    except Exception as e:
        logger.warning(f"No se pudo procesar el JSON local ({e}).")

    if not unique_cards_map and not query_raw:
        try:
            api_data = fetch_cards("set.id:sv01")
            for card in api_data:
                unique_cards_map[card.get("id")] = card
        except Exception:
            pass

    all_cards = list(unique_cards_map.values())
    for card_data in all_cards:
        resolve_card_relations(card_data)

    if all_cards:
        if selected_sort in ["price", "-price"]:
            all_cards.sort(
                key=lambda x: float(
                    extract_market_price(x.get("tcgplayer", {}).get("prices", {}))
                    if x.get("tcgplayer")
                    else (x.get("price") or 0.0)
                ),
                reverse=(selected_sort == "-price"),
            )
        elif selected_sort == "name":
            all_cards.sort(key=lambda x: x.get("name", ""))

        total_count = len(all_cards)
        total_pages = math.ceil(total_count / page_size)
        start = (current_page - 1) * page_size
        page_cards = all_cards[start : start + page_size]

        for card_data in page_cards:
            relations = resolve_card_relations(card_data)
            card_formatted = format_card(card_data)

            if not card_formatted.get("image_url"):
                card_formatted["image_url"] = card_data.get("image_url") or card_data.get(
                    "images", {}
                ).get("small", "")
            if not card_formatted.get("set_name") or card_formatted.get("set_name") == "Unknown":
                card_formatted["set_name"] = card_data.get("set_name") or card_data.get(
                    "set", {}
                ).get("name", "Unknown")
            if not card_formatted.get("price"):
                card_formatted["price"] = (
                    extract_market_price(card_data.get("tcgplayer", {}).get("prices", {}))
                    if card_data.get("tcgplayer")
                    else card_data.get("price")
                )

            if relations.get("rarity"):
                card_formatted["rarity"] = relations["rarity"].display_name
            if relations.get("artist"):
                card_formatted["artist"] = relations["artist"].name
            if relations.get("supertype"):
                card_formatted["supertype"] = relations["supertype"].display_name

            card_formatted["id"] = (
                card_data.get("id") or card_data.get("pokemontcg_id") or card_data.get("card_id")
            )
            results.append(card_formatted)
    else:
        total_pages = 1

    context = {
        "results": results,
        "error": error,
        "current_page": current_page,
        "total_pages": total_pages,
        "has_next": current_page < total_pages,
        "has_previous": current_page > 1,
        "next_page": current_page + 1,
        "prev_page": current_page - 1,
        "query_raw": query_raw,
        "selected_sort": selected_sort,
        "selected_supertype_id": selected_supertype_id,
        "selected_rarity_id": selected_rarity_id,
        "selected_subtype_id": selected_subtype_id,
        "selected_artist_id": selected_artist_id,
        "options": {
            "subtypes": get_filter_options("subtypes"),
            "rarities": get_filter_options("rarities"),
            "supertypes": get_filter_options("supertypes"),
            "artists": get_filter_options("artists"),
        },
    }
    return render(request, "search.html", context)


@login_required(login_url="login")
def search_suggestions(request):
    """Proporciona sugerencias rápidas de cartas para autocompletar.

    Flujo:
    - Amplía el término de búsqueda con sinónimos y traducciones.
    - Consulta la base de datos local y, si es necesario, la API externa.
    - Devuelve hasta 10 resultados únicos ordenados por relevancia.

    Devuelve JSON con campos: `name`, `image_url`, `set_name`, `pokemontcg_id`."""
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)

    try:
        expanded_terms = get_expanded_search_terms(query)
        all_cards = []

        name_q = Q()
        for term in expanded_terms:
            name_q |= Q(name__icontains=term)

        cards_found = Card.objects.filter(name_q)[:100]
        for c in cards_found:
            all_cards.append(
                {
                    "name": c.name,
                    "image_url": c.image_url,
                    "set_name": c.set_name,
                    "pokemontcg_id": c.pokemontcg_id,
                }
            )

        if len(all_cards) < 5:
            try:
                sug_query = build_search_query(query)
                api_data = fetch_cards(sug_query)
                if api_data:
                    for api_card in api_data[:10]:
                        formatted_api = format_card(api_card)
                        all_cards.append(
                            {
                                "name": formatted_api.get("name"),
                                "image_url": formatted_api.get("image_url"),
                                "set_name": formatted_api.get("set_name"),
                                "pokemontcg_id": formatted_api.get("id"),
                            }
                        )
            except Exception:
                pass

        seen_ids = set()
        unique_cards = []
        for card in all_cards:
            card_id = card.get("pokemontcg_id")
            if card_id not in seen_ids:
                seen_ids.add(card_id)
                unique_cards.append(card)

        def score_card(card):
            """Calcula una puntuación de relevancia simple para ordenar sugerencias.

            Devuelve 0 si el nombre empieza por la query, 1 si la query está
            contenida en el nombre, y 2 en caso contrario. Menor es mejor."""
            name_lower = card.get("name", "").lower()
            q_lower = query.lower()
            return 0 if name_lower.startswith(q_lower) else (1 if q_lower in name_lower else 2)

        unique_cards.sort(key=score_card)
        unique_cards = unique_cards[:10]

        results = [
            {
                "name": c.get("name"),
                "image": c.get("image_url"),
                "image_url": c.get("image_url"),
                "set": c.get("set_name"),
                "pokemontcg_id": c.get("pokemontcg_id"),
            }
            for c in unique_cards
        ]
        return JsonResponse(results, safe=False)
    except Exception:
        return JsonResponse({"error": "Internal server error"}, status=500)


@login_required(login_url="login")
@require_POST
def create_alert(request):
    """Crea una alerta de precio para la carta indicada por el usuario.

    Valida el porcentaje de descuento y el precio actual, sincroniza la carta
    con la API si no existe localmente, y almacena la alerta activa en la DB."""
    pokemontcg_id = request.POST.get("pokemontcg_id")
    discount_percentage = request.POST.get("discount_percentage")
    current_price_str = request.POST.get("current_price")

    if not pokemontcg_id or not discount_percentage or current_price_str == "N/A":
        messages.error(request, "No se puede crear una alerta sin un precio válido.")
        return redirect("search")

    try:
        discount = int(discount_percentage)
        current_price = float(current_price_str)
        target_price = current_price * (1 - (discount / 100))

        card = Card.objects.filter(pokemontcg_id=pokemontcg_id).first()
        if not card:
            card_data = fetch_card(pokemontcg_id)
            if card_data:
                relations = resolve_card_relations(card_data)
                formatted = format_card(card_data)
                card = Card.objects.create(
                    pokemontcg_id=pokemontcg_id,
                    name=formatted.get("name"),
                    image_url=formatted.get("image_url")
                    or formatted.get("images", {}).get("small", ""),
                    set_name=formatted.get("set_name"),
                    number=formatted.get("number"),
                    price=formatted.get("price") or current_price,
                    **relations,
                )
            else:
                messages.error(request, "No se pudo obtener la carta de la API.")
                return redirect("search")

        PriceAlert.objects.create(
            user=request.user,
            card=card,
            discount_percentage=discount,
            target_price=round(target_price, 2),
            is_active=True,
        )
        messages.success(request, f"Alerta creada para ${round(target_price, 2)}.")
        return redirect("dashboard")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect("search")


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def edit_alert(request, alert_id):
    """Permite editar el porcentaje de descuento de una alerta existente.

    Actualiza el `discount_percentage` y recalcula el `target_price` sobre el
    precio base de la carta, mostrando el histórico de precios disponibles."""
    alert = get_object_or_404(PriceAlert, id=alert_id, user=request.user)
    historial = PriceHistory.objects.filter(card=alert.card).order_by("recorded_at")

    if request.method == "POST":
        discount_percentage = request.POST.get("discount_percentage")
        if discount_percentage and discount_percentage.isdigit():
            nuevo_porcentaje = int(discount_percentage)
            alert.discount_percentage = nuevo_porcentaje

            precio_base = float(alert.card.price or 0.0)
            alert.target_price = precio_base * (1.0 - (nuevo_porcentaje / 100.0))
            # -----------------------------------------------------------------

            alert.save()
            messages.success(request, "Alerta y precio objetivo actualizados correctamente.")
            return redirect("dashboard")

    context = {
        "alert": alert,
        "price_dates": [h.recorded_at.strftime("%Y-%m-%d") for h in historial],
        "price_values": [float(h.price) for h in historial],
    }
    return render(request, "alerts/edit_alert.html", context)


@login_required(login_url="login")
def card_detail(request, card_id):
    """Renderiza el detalle de una carta Pokémon TCG.
    Aplica una estrategia de tres capas: Caché -> DB Local -> API/JSON Externo.
    Garantiza el registro histórico diario bajo demanda para poblar el gráfico de precios."""
    if not card_id:
        return render(
            request,
            "card_detail.html",
            {"card": {}, "market_price": "N/A", "error": "Identificador de carta no válido."},
        )

    # 1. Estrategia de Caché Dinámica
    cache_key = f"card_detail_{card_id}"
    cached_context = cache.get(cache_key)
    if cached_context:
        logger.info(f"[CACHE HIT] Sirviendo detalles para la carta: {card_id}")
        # Garantizar que exista un punto histórico para hoy aunque vengamos de la caché.
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
                    # Invalidar la caché para forzar una próxima recarga fresca
                    try:
                        cache.delete(cache_key)
                    except Exception:
                        pass
                    logger.info(
                        f"[CACHE FIX] Creado PriceHistory desde caché para {card_id}: ${price_from_cache}"
                    )
        except Exception as e:
            logger.warning(f"[CACHE FIX] No se pudo asegurar PriceHistory desde caché: {e}")

        return render(request, "card_detail.html", cached_context)

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

    # Criterio estricto de integridad para datos locales
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

    if not error and card_obj and final_parsed_price > 0:
        hoy = timezone.now().date()
        ya_existe_hoy = PriceHistory.objects.filter(card=card_obj, recorded_at__date=hoy).exists()

        if not ya_existe_hoy:
            PriceHistory.objects.create(
                card=card_obj, price=final_parsed_price, marketplace="tcgplayer"
            )
            logger.info(
                f"[📉 CHART UPDATE] Nuevo punto histórico creado hoy para {card_id}: ${final_parsed_price}"
            )

    # 5. Despacho y Almacenamiento en Caché del Contexto Final
    context = {"card": card_data_payload, "market_price": market_price, "error": error}

    if not error and card_data_payload:
        # Almacenamiento TTL por 24 Horas
        cache.set(cache_key, context, 60 * 60 * 24)

    return render(request, "card_detail.html", context)


@login_required
@require_POST
def delete_alert(request, alert_id):
    """Elimina una `PriceAlert` propiedad del usuario autenticado.

    Valida la pertenencia (seguridad) y borra el registro. Redirige al
    dashboard mostrando un mensaje de confirmación."""
    alert = get_object_or_404(PriceAlert, id=alert_id, user=request.user)
    alert.delete()
    messages.success(request, "Alerta personalizada eliminada correctamente.")
    return redirect("dashboard")


@require_GET
def card_price_history(_request, card_id):
    """Devuelve los datos de evolución de precios de los últimos 30 días para el gráfico."""
    try:
        card = Card.objects.get(pokemontcg_id=card_id)
        last_30_days = timezone.now() - timedelta(days=30)
        history = PriceHistory.objects.filter(card=card, recorded_at__gte=last_30_days).order_by(
            "recorded_at"
        )

        return JsonResponse(
            {
                "dates": [h.recorded_at.strftime("%d/%m") for h in history],
                "prices": [float(h.price) for h in history],
                "card_name": card.name,
            }
        )
    except Card.DoesNotExist:
        return JsonResponse({"error": "Carta no encontrada"}, status=404)


def market_trends(request):
    """Muestra un ranking de las cartas con mayor variación de precio
    en los últimos 7 días, calculado a partir de PriceHistory."""
    hace_7_dias = timezone.now() - timedelta(days=30)

    cartas_con_historial = []
    cartas = Card.objects.exclude(price__isnull=True)

    for carta in cartas:
        precio_antiguo = (
            PriceHistory.objects.filter(card=carta, recorded_at__gte=hace_7_dias)
            .order_by("recorded_at")
            .first()
        )
        if precio_antiguo and precio_antiguo.price:
            variacion = ((carta.price - precio_antiguo.price) / precio_antiguo.price) * 100
            cartas_con_historial.append(
                {
                    "carta": carta,
                    "precio_actual": carta.price,
                    "variacion": round(variacion, 1),
                }
            )
    cartas_con_historial = [c for c in cartas_con_historial if c["variacion"] != 0]
    subidas = [c for c in cartas_con_historial if c["variacion"] > 0]
    bajadas = [c for c in cartas_con_historial if c["variacion"] < 0]

    top_subidas = sorted(subidas, key=lambda x: x["variacion"], reverse=True)[:5]
    top_bajadas = sorted(bajadas, key=lambda x: x["variacion"])[:5]
    contexto = {
        "total_cartas": Card.objects.count(),
        "top_subidas": top_subidas,
        "top_bajadas": top_bajadas,
    }
    return render(request, "market_trends.html", contexto)
