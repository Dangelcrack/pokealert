import os
import math
import json
import logging  # 🌟 Corregido: Uso del sistema de logs estándar de Python
import unicodedata
import requests
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

from cards.services.pokemontcg_service import fetch_cards, fetch_card, search_cards
from cards.services.card_formatter import format_card
from alerts.models import PriceAlert, PriceHistory
from cards.utils import POKEMON_ES_TO_TCG, TCG_TERMS
from .models import Card, Rarity, Supertype, Subtype, Artist, PokemonEspecie
from .serializers import CardSerializer

# Configuración del logger para rastrear eventos en consola
logger = logging.getLogger(__name__)

# ==========================================
# FUNCIONES AUXILIARES Y DE CONFIGURACIÓN
# ==========================================

def warm_up_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM cards_card")
    except Exception:
        pass


def safe_append(query_parts, model, id_value, label, field):
    try:
        obj = model.objects.get(id=id_value)
        query_parts.append(f'{label}:"{getattr(obj, field)}"')
    except model.DoesNotExist:
        return


def build_search_query(query_raw: str, rarity=None, supertype=None, subtype=None, artist=None) -> str:
    """
    Abstrae la lógica de construcción de consultas para la API de Pokémon TCG.
    Traduce términos y concatena filtros en formato Lucene (AND).
    """
    query_parts = []
    
    if query_raw:
        lookup = query_raw.lower()
        term = (
            POKEMON_ES_TO_TCG.get(lookup)
            or TCG_TERMS.get(lookup)
            or query_raw
        )
        # 🌟 Corregido: Evita las comillas si es una sola palabra para acelerar la API externa
        if " " in term:
            query_parts.append(f'name:"{term}"')
        else:
            query_parts.append(f'name:{term}')

    if rarity:
        safe_append(query_parts, Rarity, rarity, "rarity", "name")

    if supertype:
        safe_append(query_parts, Supertype, supertype, "supertype", "name")

    if subtype:
        safe_append(query_parts, Subtype, subtype, "subtypes", "name")

    if artist:
        safe_append(query_parts, Artist, artist, "artist", "name")

    return " AND ".join(query_parts)


def normalize(text):
    """Quita acentos y pasa a minúsculas."""
    if not text:
        return ""
    text = text.lower().strip()
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def translate_query(query_raw: str) -> str:
    """
    Traduce consultas en español a inglés.
    Estrategia: BD (PokemonEspecie) → Diccionario TCG_TERMS
    """
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


def get_filter_options(filter_name=None):
    cache_key = 'filter_options_all'
    filters = cache.get(cache_key)
    
    if filters is None:
        filters = {
            'supertypes': list(Supertype.objects.all().order_by('display_name')),
            'subtypes': list(Subtype.objects.all().order_by('display_name')),
            'rarities': list(Rarity.objects.all().order_by('display_name')),
            'artists': list(Artist.objects.all().order_by('name')),
        }
        cache.set(cache_key, filters, 3600)

    if filter_name:
        return filters.get(filter_name)

    return filters


def extract_market_price(prices: dict):
    """Devuelve el mejor precio disponible de la carta."""
    if not prices:
        return None

    for t in ["holofoil", "normal", "reverseHolofoil"]:
        if t in prices:
            price = prices[t].get("market")
            if price:
                return float(price)

    return None


def safe_price(price):
    return float(price) if isinstance(price, (int, float)) else float('inf')


def format_card(card_data: dict):
    """ Normaliza los datos crudos de la API a un diccionario consistente. """
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
    """ Resuelve las ForeignKeys de una carta desde datos de API. """
    relations = {}

    if card_data.get('rarity'):
        rarity, _ = Rarity.objects.get_or_create(
            name=normalize(card_data['rarity']),
            defaults={'display_name': card_data['rarity']}
        )
        relations['rarity'] = rarity

    if card_data.get('supertype'):
        supertype, _ = Supertype.objects.get_or_create(
            name=normalize(card_data['supertype']),
            defaults={'display_name': card_data['supertype']}
        )
        relations['supertype'] = supertype

    if card_data.get('subtypes') and isinstance(card_data['subtypes'], list):
        subtype_name = card_data['subtypes'][0] if card_data['subtypes'] else None
        if subtype_name:
            subtype, _ = Subtype.objects.get_or_create(
                name=normalize(subtype_name),
                defaults={'display_name': subtype_name}
            )
            relations['subtype'] = subtype

    if card_data.get('artist'):
        artist, _ = Artist.objects.get_or_create(name=card_data['artist'])
        relations['artist'] = artist

    if card_data.get('name'):
        pokemon = PokemonEspecie.objects.filter(
            Q(name_en__icontains=card_data['name']) |
            Q(name_es__icontains=card_data['name'])
        ).first()
        if pokemon:
            relations['pokemon_especie'] = pokemon

    return relations

# ==========================================
# VIEWSETS Y VISTAS DE AUTENTICACIÓN
# ==========================================

class CardViewSet(viewsets.ModelViewSet):
    queryset = Card.objects.all()
    serializer_class = CardSerializer
    search_fields = ['name']
    filterset_fields = ['rarity', 'supertype', 'subtype', 'artist']


def home(request):
    return render(request, 'home.html')


@require_http_methods(["GET", "POST"])
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if password != password_confirm:
            return render(request, 'auth/register.html', {'error': 'Las contraseñas no coinciden'})

        if User.objects.filter(username=username).exists():
            return render(request, 'auth/register.html', {'error': 'El usuario ya existe'})

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        return redirect('home')

    return render(request, 'auth/register.html')


@require_http_methods(["GET", "POST"])
def user_login(request):
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )

        if user:
            login(request, user)
            return redirect('home')

        return render(request, 'auth/login.html', {'error': 'Usuario o contraseña incorrectos'})

    return render(request, 'auth/login.html')


def user_logout(request):
    logout(request)
    return redirect('home')


@login_required(login_url='login')
def dashboard(request):
    alerts = request.user.alerts.all()
    return render(request, 'dashboard.html', {'alerts': alerts})

# ==========================================
# VISTAS PRINCIPALES DE LA APLICACIÓN
# ==========================================

@login_required(login_url='login')
def search(request):
    # 1. Parámetros y Preparación
    query_raw = request.GET.get('q', '').strip()
    selected_sort = request.GET.get('sort', '')
    selected_supertype_id = request.GET.get('supertype', '')
    selected_rarity_id = request.GET.get('rarity', '')
    selected_subtype_id = request.GET.get('subtype', '')
    selected_artist_id = request.GET.get('artist', '')
    
    page_param = request.GET.get('page')
    current_page = max(1, int(page_param) if page_param and page_param.isdigit() else 1)
    page_size = 24

    api_query = build_search_query(
        query_raw,
        rarity=selected_rarity_id,
        supertype=selected_supertype_id,
        subtype=selected_subtype_id,
        artist=selected_artist_id
    )

    error = None 
    results = []
    total_pages = 1
    all_cards = []

    # 3. Flujo Híbrido Inteligente: JSON Local -> Fallback a API
    try:
        json_path = os.path.join(settings.BASE_DIR, "todas_las_cartas_tcg.json")
        json_loaded = False
        local_cards = []

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data_cargada = json.load(f)
                if isinstance(data_cargada, dict):
                    local_cards = data_cargada.get("data", list(data_cargada.values()))
                else:
                    local_cards = data_cargada
                json_loaded = True
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"⚠️ Alerta: No se pudo leer el JSON local ({e}). Forzando API...")

        if json_loaded:
            if query_raw or selected_rarity_id or selected_supertype_id or selected_subtype_id or selected_artist_id:
                filtered_cards = []
                target_name = None
                if query_raw:
                    lookup = query_raw.lower()
                    target_name = POKEMON_ES_TO_TCG.get(lookup) or TCG_TERMS.get(lookup) or query_raw

                target_rarity = Rarity.objects.filter(id=selected_rarity_id).first().name if selected_rarity_id else None
                target_supertype = Supertype.objects.filter(id=selected_supertype_id).first().name if selected_supertype_id else None
                target_subtype = Subtype.objects.filter(id=selected_subtype_id).first().name if selected_subtype_id else None
                target_artist = Artist.objects.filter(id=selected_artist_id).first().name if selected_artist_id else None

                for card in local_cards:
                    match = True
                    if target_name and target_name.lower() not in card.get("name", "").lower():
                        match = False
                    if target_rarity and card.get("rarity") != target_rarity:
                        match = False
                    if target_supertype and card.get("supertype") != target_supertype:
                        match = False
                    if target_artist and card.get("artist") != target_artist:
                        match = False
                    if target_subtype:
                        subtypes_list = card.get("subtypes", [])
                        if isinstance(subtypes_list, str):
                            subtypes_list = [subtypes_list]
                        if target_subtype not in subtypes_list:
                            match = False
                    
                    if match:
                        filtered_cards.append(card)

                if filtered_cards:
                    all_cards = filtered_cards
                else:
                    if api_query:
                        all_cards = fetch_cards(api_query)
                    else:
                        all_cards = []
            else:
                all_cards = local_cards
        else:
            if api_query:
                all_cards = fetch_cards(api_query)
            else:
                all_cards = fetch_cards("set.id:sv01")

        # 🌟 🛡️ NUEVO SISTEMA DE SEGURIDAD INTERNA (DB LOCAL BACKUP):
        # Si las búsquedas anteriores quedaron vacías (ej: por Timeout de la API), buscamos en la base de datos local
        if not all_cards and (query_raw or selected_rarity_id or selected_supertype_id or selected_subtype_id or selected_artist_id):
            logger.warning(f"⚠️ La API externa falló o dio Timeout. Activando plan de contingencia con la base de datos local.")
            db_filters = Q()
            if query_raw:
                translated = translate_query(query_raw)
                db_filters &= (Q(name__icontains=query_raw) | Q(name__icontains=translated))
            if selected_rarity_id:
                db_filters &= Q(rarity_id=selected_rarity_id)
            if selected_supertype_id:
                db_filters &= Q(supertype_id=selected_supertype_id)
            if selected_subtype_id:
                db_filters &= Q(subtype_id=selected_subtype_id)
            if selected_artist_id:
                db_filters &= Q(artist_id=selected_artist_id)

            db_results = Card.objects.filter(db_filters).select_related("rarity", "supertype", "subtype", "artist")[:100]
            
            # Convertimos los objetos de la BD al formato diccionario que espera el resto de la vista
            for c in db_results:
                all_cards.append({
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
                })

        # 4. Ordenamiento y Paginación en memoria
        if all_cards:
            if selected_sort in ["price", "-price"]:
                all_cards.sort(
                    key=lambda x: float(
                        extract_market_price(x.get("tcgplayer", {}).get("prices", {})) 
                        if x.get("tcgplayer") else (x.get("price") or 0.0)
                    ),
                    reverse=(selected_sort == "-price"),
                )
            elif selected_sort == "name":
                all_cards.sort(key=lambda x: x.get("name", ""))

            total_count = len(all_cards)
            total_pages = math.ceil(total_count / page_size)

            start = (current_page - 1) * page_size
            end = start + page_size
            page_cards = all_cards[start:end]

            # 5. Formateo y Normalización Universal
            for card_data in page_cards:
                relations = resolve_card_relations(card_data)
                card_formatted = format_card(card_data)

                if not card_formatted.get("image_url"):
                    card_formatted["image_url"] = card_data.get("image_url") or card_data.get("images", {}).get("small", "")
                    
                if not card_formatted.get("set_name") or card_formatted.get("set_name") == "Unknown":
                    card_formatted["set_name"] = card_data.get("set_name") or card_data.get("set", {}).get("name", "Unknown")

                if not card_formatted.get("price"):
                    price_extracted = extract_market_price(card_data.get("tcgplayer", {}).get("prices", {})) if card_data.get("tcgplayer") else None
                    card_formatted["price"] = price_extracted or card_data.get("price")

                if relations.get("rarity"):
                    card_formatted["rarity"] = relations["rarity"].display_name
                elif not card_formatted.get("rarity"):
                    card_formatted["rarity"] = card_data.get("rarity")

                if relations.get("artist"):
                    card_formatted["artist"] = relations["artist"].name
                elif not card_formatted.get("artist"):
                    card_formatted["artist"] = card_data.get("artist")

                if relations.get("supertype"):
                    card_formatted["supertype"] = relations["supertype"].display_name
                elif not card_formatted.get("supertype"):
                    card_formatted["supertype"] = card_data.get("supertype")

                card_formatted["id"] = (
                    card_data.get("id")
                    or card_data.get("pokemontcg_id")
                    or card_data.get("card_id")
                )
                results.append(card_formatted)
        else:
            total_count = 0
            total_pages = 1

    except requests.RequestException as e:
        error = f"Error al conectar con la API: {e}"

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
        }
    }
    return render(request, "search.html", context)


@login_required(login_url='login')
@require_POST
def create_alert(request):
    """Crea alerta de precio utilizando la función centralizada de servicio fetch_card."""
    pokemontcg_id = request.POST.get('pokemontcg_id')
    discount_percentage = request.POST.get('discount_percentage')
    current_price_str = request.POST.get('current_price')

    if not pokemontcg_id or not discount_percentage or current_price_str == 'N/A':
        messages.error(request, '❌ No se puede crear una alerta sin un precio válido.')
        return redirect('search')

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
                    image_url=formatted.get("image_url") or formatted.get("images", {}).get("small", ""),
                    set_name=formatted.get("set_name"),
                    number=formatted.get("number"),
                    price=formatted.get("price") or current_price,
                    rarity=relations.get("rarity"),
                    supertype=relations.get("supertype"),
                    subtype=relations.get("subtype"),
                    artist=relations.get("artist"),
                    pokemon_especie=relations.get("pokemon_especie")
                )
            else:
                messages.error(request, '❌ No se pudo obtener la carta de la API centralizada.')
                return redirect('search')

        PriceAlert.objects.create(
            user=request.user,
            card=card,
            discount_percentage=discount,
            target_price=round(target_price, 2),
            is_active=True
        )
        
        messages.success(request, f'✅ Alerta creada. Te avisaremos cuando baje de ${round(target_price, 2)}.')
        return redirect('dashboard')

    except (ValueError, TypeError) as e:
        messages.error(request, f'❌ Datos inválidos: {str(e)}')
        return redirect('search')
    except Exception as e:
        messages.error(request, f'❌ Error: {str(e)}')
        return redirect('search')


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def edit_alert(request, alert_id):
    alert = get_object_or_404(PriceAlert, id=alert_id, user=request.user)
    historial = PriceHistory.objects.filter(card=alert.card).order_by('recorded_at')
    
    if request.method == 'POST':
        discount_percentage = request.POST.get('discount_percentage')
        if discount_percentage and discount_percentage.isdigit():
            alert.discount_percentage = int(discount_percentage)
            alert.save()
            messages.success(request, '✅ Alerta actualizada correctamente.')
            return redirect('dashboard')

    context = {
        'alert': alert,
        'price_dates': [h.recorded_at.strftime('%Y-%m-%d') for h in historial],
        'price_values': [float(h.price) for h in historial],
    }
    return render(request, 'alerts/edit_alert.html', context)


@login_required(login_url='login')
def search_suggestions(request):
    """Sugerencias de búsqueda homogéneas mezclando la BD y el servicio fetch_cards."""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)
    
    try:
        query_norm = normalize(query)
        traducciones_encontradas = set()
        
        for es_key, en_value in POKEMON_ES_TO_TCG.items():
            if es_key.startswith(query_norm):
                traducciones_encontradas.add(en_value)
        
        for es_key, en_value in TCG_TERMS.items():
            if es_key.startswith(query_norm):
                traducciones_encontradas.add(en_value)
        
        all_cards = []
        traducciones_sin_cartas = set()
        
        if traducciones_encontradas:
            for translation in traducciones_encontradas:
                cards_found = Card.objects.filter(name__icontains=translation)[:50]
                found_count = cards_found.count()
                
                for c in cards_found:
                    all_cards.append({
                        "name": c.name,
                        "image_url": c.image_url,
                        "set_name": c.set_name,
                        "pokemontcg_id": c.pokemontcg_id
                    })
                
                if found_count == 0:
                    traducciones_sin_cartas.add(translation)
        
        if not all_cards:
            exact_translation = POKEMON_ES_TO_TCG.get(query_norm, None)
            if exact_translation:
                cards_found = Card.objects.filter(name__icontains=exact_translation)[:100]
                if cards_found.count() == 0:
                    traducciones_sin_cartas.add(exact_translation)
                else:
                    for c in cards_found:
                        all_cards.append({
                            "name": c.name,
                            "image_url": c.image_url,
                            "set_name": c.set_name,
                            "pokemontcg_id": c.pokemontcg_id
                        })
            else:
                cards_found = Card.objects.filter(name__icontains=query)[:100]
                for c in cards_found:
                    all_cards.append({
                        "name": c.name,
                        "image_url": c.image_url,
                        "set_name": c.set_name,
                        "pokemontcg_id": c.pokemontcg_id
                    })
        
        # Fallback dinámico a la API Externa si hay pocos resultados locales
        if len(all_cards) < 5 and traducciones_sin_cartas:
            for translation in traducciones_sin_cartas:
                try:
                    sug_query = build_search_query(translation)
                    api_data = fetch_cards(sug_query)
                    if api_data:
                        for api_card in api_data[:10]:
                            formatted_api = format_card(api_card)
                            all_cards.append({
                                "name": formatted_api.get("name"),
                                "image_url": formatted_api.get("image_url"),
                                "set_name": formatted_api.get("set_name"),
                                "pokemontcg_id": formatted_api.get("id")
                            })
                except Exception:
                    continue
        
        # Eliminar duplicados manteniendo consistencia por id de la API
        seen_ids = set()
        unique_cards = []
        for card in all_cards:
            card_id = card.get('pokemontcg_id')
            if card_id not in seen_ids:
                seen_ids.add(card_id)
                unique_cards.append(card)
        
        # Sistema de scoring para priorizar coincidencia inicial exacta
        def score_card(card):
            name_lower = card.get('name', '').lower()
            q_lower = query.lower()
            if name_lower.startswith(q_lower):
                return 0
            elif q_lower in name_lower:
                return 1
            return 2
        
        unique_cards.sort(key=score_card)
        unique_cards = unique_cards[:10]
        
        # Construir respuesta JSON compatible con Javascript
        results = []
        for card in unique_cards:
            results.append({
                "name": card.get("name"),
                "image": card.get("image_url"),
                "image_url": card.get("image_url"),
                "set": card.get("set_name"),
                "pokemontcg_id": card.get("pokemontcg_id")
            })
        
        return JsonResponse(results, safe=False)
    except Exception:
        logger.exception("Error en search view de sugerencias")
        return JsonResponse({"error": "Internal server error"}, status=500)
    

@login_required(login_url="login")
def card_detail(request, card_id):
    if not card_id:
        return render(
            request,
            "card_detail.html",
            {
                "card": {},
                "market_price": "N/A",
                "error": "Carta no válida.",
            },
        )

    cache_key = f"card_detail_{card_id}"
    cached = cache.get(cache_key)
    if cached:
        return render(request, "card_detail.html", cached)

    error = None
    card = {}
    market_price = "N/A"

    # 1. Base de datos primero
    card_obj = (
        Card.objects.select_related(
            "rarity",
            "supertype",
            "subtype",
            "artist",
            "pokemon_especie",
        )
        .filter(pokemontcg_id=card_id)
        .first()
    )

    if card_obj:
        price = float(card_obj.price or 0)
        card = {
            "id": card_obj.pokemontcg_id,
            "name": card_obj.name,
            "images": {
                "small": card_obj.image_url,
                "large": card_obj.image_url,
            },
            "price": price,
            "rarity": card_obj.rarity.display_name if card_obj.rarity else "N/A",
            "artist": card_obj.artist.name if card_obj.artist else "Desconocido",
            "supertype": card_obj.supertype.display_name if card_obj.supertype else "N/A",
            "subtype": card_obj.subtype.display_name if card_obj.subtype else "N/A",
            "pokemon": card_obj.pokemon_especie.name_en if card_obj.pokemon_especie else None,
            "set": {"name": card_obj.set_name},
            "number": card_obj.number,
        }
        market_price = f"{price:.2f}"
    else:
        # 2. API fallback limpio
        try:
            data = fetch_card(card_id)
            if not data:
                error = "La carta no existe en la API."
            else:
                relations = resolve_card_relations(data)
                card = format_card(data)

                # override relaciones (BD enrich)
                if relations.get("rarity"):
                    card["rarity"] = relations["rarity"].display_name
                if relations.get("artist"):
                    card["artist"] = relations["artist"].name
                if relations.get("supertype"):
                    card["supertype"] = relations["supertype"].display_name
                if relations.get("subtype"):
                    card["subtype"] = relations["subtype"].display_name
                if relations.get("pokemon_especie"):
                    card["pokemon"] = relations["pokemon_especie"].name_en

                market_price = f"{card['price']:.2f}"

                # persistencia BD
                Card.objects.get_or_create(
                    pokemontcg_id=data["id"],
                    defaults={
                        "name": card["name"],
                        "image_url": card["image_url"],
                        "set_name": card.get("set_name"),
                        "number": card.get("number"),
                        "price": card.get("price"),
                        **relations,
                    },
                )
        except Exception as e:
            error = f"Error al obtener carta: {str(e)}"

    context = {
        "card": card,
        "market_price": market_price,
        "error": error,
    }

    if not error:
        cache.set(cache_key, context, 60 * 60 * 24)

    return render(request, "card_detail.html", context)


@login_required
@require_POST
def delete_alert(request, alert_id):
    alert = get_object_or_404(PriceAlert, id=alert_id, user=request.user)
    alert.delete()
    messages.success(request, '✅ Alerta personalizada eliminada correctamente.')
    return redirect('dashboard')


@require_GET
def card_price_history(_request, card_id):
    try:
        card = Card.objects.get(pokemontcg_id=card_id)
        last_30_days = timezone.now() - timedelta(days=30)
        
        history = PriceHistory.objects.filter(
            card=card,
            recorded_at__gte=last_30_days
        ).order_by('recorded_at')
        
        return JsonResponse({
            'dates': [h.recorded_at.strftime('%d/%m') for h in history],
            'prices': [float(h.price) for h in history],
            'card_name': card.name
        })
    except Card.DoesNotExist:
        return JsonResponse({'error': 'Carta no encontrada'}, status=404)