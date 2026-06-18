import os
import requests
import math
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets
from django.db.models import Count
from .models import Card, PokemonEspecie
from .serializers import CardSerializer


class CardViewSet(viewsets.ModelViewSet):
    queryset = Card.objects.all()
    serializer_class = CardSerializer
    search_fields = ['name', 'rarity']
    filterset_fields = ['rarity']


def test_pokemon_api(request):
    card_id = "base1-4"
    url = f"https://api.pokemontcg.io/v2/cards/{card_id}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {})
            prices = data.get('tcgplayer', {}).get('prices', {})
            
            return JsonResponse({
                'status': '¡Conectado con éxito! ✅',
                'name': data.get('name'),
                'rarity': data.get('rarity'),
                'prices': prices
            })
        return JsonResponse({'error': 'No se encontró la carta o la API falló'}, status=response.status_code)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'auth/login.html', {'error': 'Usuario o contraseña incorrectos'})

    return render(request, 'auth/login.html')


def user_logout(request):
    logout(request)
    return redirect('home')


@login_required(login_url='login')
def dashboard(request):
    alerts = request.user.alerts.all()
    return render(request, 'dashboard.html', {'alerts': alerts})


@login_required(login_url='login')
def search(request):
    query = request.GET.get('q', '').strip()
    results = []
    error = None
    
    try:
        current_page = int(request.GET.get('page', 1))
        if current_page < 1:
            current_page = 1
    except ValueError:
        current_page = 1

    page_size = 24  
    has_next = False
    has_previous = current_page > 1
    total_count = 0
    total_pages = 1

    if query:
        try:
            url = f"https://api.pokemontcg.io/v2/cards"
            api_key = os.getenv('POKEMON_TCG_API_KEY')
            
            headers = {}
            if api_key:
                headers['X-Api-Key'] = api_key
                
            params = {
                'q': f'name:{query}',
                'page': current_page,
                'pageSize': page_size
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                cards_data = data.get('data', [])
                total_count = data.get('totalCount', 0)  # 📊 El número total real en la API (ej: 1700)
                
                # 📐 Calculamos el número total de páginas (ej: 1700 / 24 = 70.8 -> 71 páginas)
                total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
                
                has_next = (current_page * page_size) < total_count
                
                for card in cards_data:
                    tcgplayer_prices = card.get('tcgplayer', {}).get('prices', {})
                    market_price = None
                    
                    if 'holofoil' in tcgplayer_prices:
                        market_price = tcgplayer_prices['holofoil'].get('market')
                    elif 'normal' in tcgplayer_prices:
                        market_price = tcgplayer_prices['normal'].get('market')
                    
                    results.append({
                        'id': card.get('id'),
                        'name': card.get('name'),
                        'image': card.get('images', {}).get('small', ''),
                        'rarity': card.get('rarity', 'N/A'),
                        'price': market_price or 'N/A',
                        'set_name': card.get('set', {}).get('name', 'Unknown'),
                    })
            else:
                error = f"La API de Pokémon TCG está experimentando demoras (Código {response.status_code})."
        
        except requests.exceptions.Timeout:
            error = "⏱️ El servidor externo de Pokémon TCG tardó demasiado en responder. Vuelve a intentarlo ahora."
        except Exception as e:
            error = f"Error conectando con la API: {str(e)}"
            
    else:
        # Bloque de populares intacto
        top_cards = Card.objects.annotate(
            alert_count=Count('alerts')
        ).filter(alert_count__gt=0).order_by('-alert_count')[:8]
        
        api_key = os.getenv('POKEMON_TCG_API_KEY')
        headers = {'X-Api-Key': api_key} if api_key else {}
        
        for card in top_cards:
            market_price = 'N/A'
            try:
                url = f"https://api.pokemontcg.io/v2/cards/{card.pokemontcg_id}"
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    api_data = response.json().get('data', {})
                    tcgplayer_prices = api_data.get('tcgplayer', {}).get('prices', {})
                    if 'holofoil' in tcgplayer_prices:
                        market_price = tcgplayer_prices['holofoil'].get('market')
                    elif 'normal' in tcgplayer_prices:
                        market_price = tcgplayer_prices['normal'].get('market')
                    market_price = market_price or 'N/A'
            except Exception:
                market_price = 'N/A'
            
            results.append({
                'id': card.pokemontcg_id,
                'name': card.name,
                'image': card.image_url,
                'rarity': card.get_rarity_display(),
                'price': market_price,
                'set_name': 'Popular',
                'is_popular': True
            })

    # Creamos un rango de páginas en Django para iterar fácilmente en el HTML (ej: [1, 2, 3, ..., 71])
    # Si hay demasiadas páginas (ej: más de 7), mostramos solo un bloque inteligente
    page_range = range(1, total_pages + 1)

    return render(request, 'search.html', {
        'query': query,
        'results': results,
        'error': error,
        'is_popular': not query and results,
        'current_page': current_page,
        'has_next': has_next,
        'has_previous': has_previous,
        'next_page': current_page + 1,
        'prev_page': current_page - 1,
        'total_count': total_count,      # 👈 Enviado al HTML
        'total_pages': total_pages,      # 👈 Enviado al HTML
        'page_range': page_range,        # 👈 Enviado al HTML
    })

@login_required(login_url='login')
@require_http_methods(["POST"])
def create_alert(request):
    from alerts.models import PriceAlert
    from alerts.serializers import PriceAlertSerializer
    
    pokemontcg_id = request.POST.get('pokemontcg_id')
    discount_percentage = request.POST.get('discount_percentage')

    if not pokemontcg_id or not discount_percentage:
        messages.error(request, '❌ Faltan datos para crear la alerta.')
        return redirect('search')

    try:
        serializer_data = {
            'pokemontcg_id': pokemontcg_id,
            'discount_percentage': int(discount_percentage)
        }
        
        class FakeRequest:
            def __init__(self, user):
                self.user = user
        
        serializer = PriceAlertSerializer(
            data=serializer_data,
            context={'request': FakeRequest(request.user)}
        )
        
        if serializer.is_valid():
            serializer.save()
            messages.success(request, '✅ ¡Alerta creada correctamente! Te notificaremos cuando baje.')
            return redirect('dashboard')
        else:
            errors = serializer.errors
            first_error = list(errors.values())[0][0] if errors else 'Error desconocido'
            messages.error(request, f'❌ {str(first_error)}')
            return redirect('search')
    
    except ValueError as e:
        messages.error(request, f'❌ Datos inválidos: {str(e)}')
        return redirect('search')
    except Exception as e:
        messages.error(request, f'❌ Error al crear la alerta: {str(e)}')
        return redirect('search')


def importar_pokemon_pokedex(request):
    """Sincroniza los Pokémon desde PokéAPI a la Base de Datos Local"""
    import requests
    from django.http import HttpResponse

    url = "https://pokeapi.co/api/v2/pokemon?limit=1025"
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            resultados = response.json().get('results', [])
            contador = 0
            for index, p in enumerate(resultados, start=1):
                nombre = p['name']
                url_imagen = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{index}.png"
                
                obj, created = PokemonEspecie.objects.get_or_create(
                    numero_pokedex=index,
                    defaults={'name': nombre, 'image': url_imagen}
                )
                if created:
                    contador += 1
            return HttpResponse(f"¡Éxito! Catálogo poblado con {contador} Pokémon.")
        return HttpResponse("❌ Error con PokéAPI", status=500)
    except Exception as e:
        return HttpResponse(f"❌ Error: {str(e)}", status=500)


@login_required(login_url='login')
def search_suggestions(request):
    """API endpoint para autocomplete usando las Especies Únicas de la BD Local"""
    query = request.GET.get('q', '').strip().lower()
    
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    sugerencias = PokemonEspecie.objects.filter(name__icontains=query)[:10]
    
    suggestions_list = []
    for pokemon in sugerencias:
        suggestions_list.append({
            'name': pokemon.name.capitalize(),
            'id': pokemon.numero_pokedex,
            'image': pokemon.image
        })
        
    return JsonResponse(suggestions_list, safe=False)