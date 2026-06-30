from datetime import timedelta, timezone
import os
import unicodedata
import requests
import math
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.core.cache import cache
from django.db import connection
from rest_framework import viewsets
from datetime import timedelta, datetime
from django.utils import timezone
from alerts.models import PriceAlert, PriceHistory
from alerts.serializers import PriceAlertSerializer
from cards.utils import POKEMON_ES_TO_TCG, TCG_TERMS
from .models import Card, Rarity, Supertype, Subtype, Artist, PokemonEspecie
from .serializers import CardSerializer

def warm_up_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM cards_card")
    except Exception:
        pass

# Asumiendo que POKEMON_ES_TO_TCG y TCG_TERMS están importados o disponibles
def normalize(text):
    """Quita acentos y minúsculas"""
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

    # 1. Buscar en PokemonEspecie por nombre español
    pokemon = PokemonEspecie.objects.filter(
        Q(name_es__icontains=q) | Q(name_en__icontains=q)
    ).first()
    
    if pokemon:
        return pokemon.name_en

    # 2. Fallback a diccionario si es necesario (menos crítico ahora)
    from cards.utils import TCG_TERMS, POKEMON_ES_TO_TCG
    
    if q in TCG_TERMS:
        return TCG_TERMS[q]

    if q in POKEMON_ES_TO_TCG:
        return POKEMON_ES_TO_TCG[q]

    # 3. Match parcial
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
        cache.set(cache_key, filters, 3600)  # Cache for 1 hour

    if filter_name:
        return filters.get(filter_name)

    return filters

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


def extract_market_price(prices: dict):
    """Devuelve el mejor precio disponible del card."""
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


def resolve_card_relations(card_data: dict):
    """
    Resuelve las ForeignKeys de una carta desde datos de API.
    Retorna un dict con las instancias resueltas.
    """
    relations = {}

    # Rarity
    if card_data.get('rarity'):
        rarity, _ = Rarity.objects.get_or_create(
            name=normalize(card_data['rarity']),
            defaults={'display_name': card_data['rarity']}
        )
        relations['rarity'] = rarity

    # Supertype
    if card_data.get('supertype'):
        supertype, _ = Supertype.objects.get_or_create(
            name=normalize(card_data['supertype']),
            defaults={'display_name': card_data['supertype']}
        )
        relations['supertype'] = supertype

    # Subtype
    if card_data.get('subtypes') and isinstance(card_data['subtypes'], list):
        # Si tiene múltiples subtypes, se guarda el primero o se puede hacer un M2M
        subtype_name = card_data['subtypes'][0] if card_data['subtypes'] else None
        if subtype_name:
            subtype, _ = Subtype.objects.get_or_create(
                name=normalize(subtype_name),
                defaults={'display_name': subtype_name}
            )
            relations['subtype'] = subtype

    # Artist
    if card_data.get('artist'):
        artist, _ = Artist.objects.get_or_create(
            name=card_data['artist']
        )
        relations['artist'] = artist

    # Pokemon Especie (búsqueda por nombre)
    if card_data.get('name'):
        pokemon = PokemonEspecie.objects.filter(
            Q(name_en__icontains=card_data['name']) |
            Q(name_es__icontains=card_data['name'])
        ).first()
        if pokemon:
            relations['pokemon_especie'] = pokemon

    return relations


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

    # 2. Construcción de Query con Traducción
    query_parts = []
    if query_raw:
        # Buscamos en el diccionario de Pokémon, luego en términos generales, 
        # y si no está en ninguno, usamos el término original.
        lookup = query_raw.lower()

        term = (
            POKEMON_ES_TO_TCG.get(lookup)
            or TCG_TERMS.get(lookup)
            or query_raw
        )
        # Usamos asteriscos para búsqueda parcial
        query_parts.append(f'name:"{term}"')
    # ... (Tus bloques try/except de filtros permanecen igual) ...
    if selected_rarity_id:
        try:
            rarity_obj = Rarity.objects.get(id=selected_rarity_id)
            query_parts.append(f'rarity:"{rarity_obj.name}"')
        except Rarity.DoesNotExist: pass
    
    if selected_supertype_id:
        try:
            supertype_obj = Supertype.objects.get(id=selected_supertype_id)
            query_parts.append(f'supertype:"{supertype_obj.name}"')
        except Supertype.DoesNotExist: pass

    if selected_subtype_id:
        try:
            subtype_obj = Subtype.objects.get(id=selected_subtype_id)
            query_parts.append(f'subtypes:"{subtype_obj.name}"')
        except Subtype.DoesNotExist: pass

    if selected_artist_id:
        try:
            artist_obj = Artist.objects.get(id=selected_artist_id)
            query_parts.append(f'artist:"{artist_obj.name}"')
        except Artist.DoesNotExist: pass

    # Inicialización de variables de estado
    error = None 
    results = []
    total_pages = 1

    # 3. Petición a API
    try:
        url = "https://api.pokemontcg.io/v2/cards"
        headers = {"X-Api-Key": os.getenv('POKEMON_TCG_API_KEY', '')}
        
        params = {
            "q": " AND ".join(query_parts) if query_parts else "name:*",
            "pageSize": 250, 
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            all_cards = data.get("data", [])
            
            # Ordenamiento
            if selected_sort in ['price', '-price']:
                all_cards.sort(
                    key=lambda x: float(extract_market_price(x.get('tcgplayer', {}).get('prices', {})) or 0.0),
                    reverse=(selected_sort == '-price')
                )
            elif selected_sort == 'name':
                all_cards.sort(key=lambda x: x.get('name', ''))

            # Paginación
            total_count = len(all_cards)
            total_pages = math.ceil(total_count / page_size)
            start = (current_page - 1) * page_size
            end = start + page_size
            page_cards = all_cards[start:end]
            
            for card_data in page_cards:
                relations = resolve_card_relations(card_data)
                price = extract_market_price(card_data.get('tcgplayer', {}).get('prices', {})) or 0.0
                
                results.append({
                    "id": card_data.get("id"),
                    "name": card_data.get("name"),
                    "images": card_data.get("images", {}),
                    "price": price,
                    "rarity": relations.get('rarity').display_name if relations.get('rarity') else "N/A",
                    "set_name": card_data.get("set", {}).get("name", "Unknown"),
                    "artist": relations.get('artist').name if relations.get('artist') else "Desconocido",
                    "supertype": relations.get('supertype').display_name if relations.get('supertype') else "N/A",
                })
        else:
            error = f"Error de API: {response.status_code}"
            
    except Exception as e:
        error = str(e)

# 5. Contexto
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
    """
    Crea alerta. Las relaciones ya se resolvieron en search.
    """
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

        # Obtener o crear carta
        card = Card.objects.filter(pokemontcg_id=pokemontcg_id).first()
        
        if not card:
            # Si no existe, consultamos API una sola vez
            api_key = os.getenv('POKEMON_TCG_API_KEY')
            headers = {'X-Api-Key': api_key} if api_key else {}
            url = f"https://api.pokemontcg.io/v2/cards/{pokemontcg_id}"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                card_data = response.json().get('data', {})
                relations = resolve_card_relations(card_data)
                
                price = extract_market_price(
                    card_data.get('tcgplayer', {}).get('prices', {})
                ) or current_price
                
                card = Card.objects.create(
                    pokemontcg_id=pokemontcg_id,
                    name=card_data.get('name', 'Unknown'),
                    image_url=card_data.get('images', {}).get('small', ''),
                    set_name=card_data.get('set', {}).get('name', 'Unknown'),
                    number=card_data.get('number', ''),
                    price=price,
                    **relations
                )
            else:
                messages.error(request, '❌ No se pudo obtener la carta de la API.')
                return redirect('search')

        # Crear alerta
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
    
    # 1. Cambiamos 'date' por 'recorded_at'
    historial = PriceHistory.objects.filter(card=alert.card).order_by('recorded_at')
    
    if request.method == 'POST':
        discount_percentage = request.POST.get('discount_percentage')
        if discount_percentage and discount_percentage.isdigit():
            alert.discount_percentage = int(discount_percentage)
            alert.save()
            messages.success(request, '✅ Alerta actualizada correctamente.')
            return redirect('dashboard')

    # 2. Cambiamos 'h.date' por 'h.recorded_at'
    context = {
        'alert': alert,
        'price_dates': [h.recorded_at.strftime('%Y-%m-%d') for h in historial],
        'price_values': [float(h.price) for h in historial],
    }
    return render(request, 'alerts/edit_alert.html', context)

@login_required(login_url='login')
def search_suggestions(request):
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
                all_cards.extend(list(cards_found))
                
                if found_count == 0:
                    traducciones_sin_cartas.add(translation)
        
        if not all_cards:
            exact_translation = POKEMON_ES_TO_TCG.get(query_norm, None)
            if exact_translation:
                all_cards = list(Card.objects.filter(name__icontains=exact_translation)[:100])
                
                if len(all_cards) == 0:
                    traducciones_sin_cartas.add(exact_translation)
            else:
                all_cards = list(Card.objects.filter(name__icontains=query)[:100])
        
        if len(all_cards) < 5 and traducciones_sin_cartas:
            api_key = os.getenv('POKEMON_TCG_API_KEY')
            headers = {'X-Api-Key': api_key} if api_key else {}
            
            for translation in traducciones_sin_cartas:
                try:
                    response = requests.get(
                        "https://api.pokemontcg.io/v2/cards",
                        params={
                            "q": f'name:"{translation}"',
                            "pageSize": 10
                        },
                        headers=headers,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        data = response.json().get("data", [])
                        
                        for api_card in data:
                            card_obj = type('APICard', (), {
                                'id': api_card.get('id'),
                                'name': api_card.get('name'),
                                'image_url': api_card.get('images', {}).get('small'),
                                'set_name': api_card.get('set', {}).get('name'),
                                'pokemontcg_id': api_card.get('id'),
                            })()
                            
                            all_cards.append(card_obj)
                
                except:
                    pass
        
        seen_ids = set()
        unique_cards = []
        for card in all_cards:
            card_id = getattr(card, 'id', None) or getattr(card, 'pokemontcg_id', None)
            if card_id not in seen_ids:
                seen_ids.add(card_id)
                unique_cards.append(card)
        
        def score_card(card):
            name_lower = card.name.lower()
            q_lower = query.lower()
            
            if name_lower.startswith(q_lower):
                return 0
            elif q_lower in name_lower:
                return 1
            else:
                return 2
        
        unique_cards.sort(key=score_card)
        unique_cards = unique_cards[:10]
        
        results = []
        for card in unique_cards:
            result = {
                "name": card.name,
                "image": getattr(card, 'image_url', None),
                "set": getattr(card, 'set_name', None),
                "pokemontcg_id": getattr(card, 'pokemontcg_id', None)
            }
            results.append(result)
        
        return JsonResponse(results, safe=False)
        
    except:
        return JsonResponse([], safe=False)


@login_required(login_url='login')
def card_detail(request, card_id):
    """
    Detalle de carta con relaciones resueltas.
    Estrategia: BD → API
    """
    error = None
    card = {}
    market_price = "N/A"
    
    # Paso 1: Intentar obtener de BD
    card_obj = Card.objects.select_related(
        'rarity', 'supertype', 'subtype', 'artist', 'pokemon_especie'
    ).filter(pokemontcg_id=card_id).first()
    
    if card_obj:
        price_val = float(card_obj.price) if card_obj.price else 0.0
        card = {
            "id": card_obj.pokemontcg_id,
            "name": card_obj.name,
            "images": {
                "small": card_obj.image_url or "",
                "large": card_obj.image_url or "",
            },
            "price": price_val,
            "rarity": card_obj.rarity.display_name if card_obj.rarity else "N/A",
            "set": {
                "name": card_obj.set_name or "Desconocido",
            },
            "artist": card_obj.artist.name if card_obj.artist else "Desconocido",
            "supertype": card_obj.supertype.display_name if card_obj.supertype else "N/A",
            "pokemon": card_obj.pokemon_especie.name_en if card_obj.pokemon_especie else None,
            "number": card_obj.number or "N/A",
        }
        market_price = f"{price_val:.2f}" if price_val else "N/A"
    else:
        # Paso 2: Obtener de API y guardar
        api_key = os.getenv('POKEMON_TCG_API_KEY')
        headers = {'X-Api-Key': api_key} if api_key else {}
        url = f"https://api.pokemontcg.io/v2/cards/{card_id}"
        
        try:
            response = requests.get(url, headers=headers, timeout=25)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                relations = resolve_card_relations(data)
                
                price = extract_market_price(
                    data.get('tcgplayer', {}).get('prices', {})
                ) or 0.0
                
                card = {
                    "id": data.get('id'),
                    "name": data.get('name'),
                    "images": {
                        "small": data.get('images', {}).get('small', ''),
                        "large": data.get('images', {}).get('large', ''),
                    },
                    "price": price,
                    "rarity": relations.get('rarity').display_name if relations.get('rarity') else "N/A",
                    "set": {
                        "name": data.get('set', {}).get('name', 'Desconocido'),
                        "series": data.get('set', {}).get('series', ''),
                    },
                    "artist": relations.get('artist').name if relations.get('artist') else "Desconocido",
                    "supertype": relations.get('supertype').display_name if relations.get('supertype') else "N/A",
                    "subtype": relations.get('subtype').display_name if relations.get('subtype') else "N/A",
                    "pokemon": relations.get('pokemon_especie').name_en if relations.get('pokemon_especie') else None,
                    "number": data.get('number', 'N/A'),
                    "hp": data.get('hp', 'N/A'),
                    "types": data.get('types', []),
                }
                
                market_price = f"{price:.2f}"
                
                # Guardar en BD
                Card.objects.create(
                    pokemontcg_id=data.get('id'),
                    name=data.get('name'),
                    image_url=data.get('images', {}).get('small'),
                    set_name=data.get('set', {}).get('name', 'Desconocido'),
                    number=data.get('number', ''),
                    price=price,
                    **relations
                )
            else:
                error = f"Carta no encontrada (Error {response.status_code})"
                
        except requests.exceptions.Timeout:
            error = "La API de Pokémon tardó demasiado. Intenta de nuevo más tarde."
        except Exception as e:
            error = f"Error inesperado: {str(e)}"
    
    context = {
        "card": card,
        "market_price": market_price,
        "error": error,
    }
    
    return render(request, 'card_detail.html', context)


@login_required
@require_POST
def delete_alert(request, alert_id):
    alert = get_object_or_404(PriceAlert, id=alert_id, user=request.user)
    alert.delete()
    messages.success(request, '✅ Alerta eliminada correctamente.')
    return redirect('dashboard')


@require_GET
def card_price_history(_request, card_id):
    """Devuelve el histórico de precios últimos 30 días en JSON"""
    
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