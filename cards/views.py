import os

import requests
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets
from django.db.models import Count
from .models import Card
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
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get('data', {})
            # Extraemos los precios de mercado
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
            return render(request, 'auth/register.html', 
                        {'error': 'Las contraseñas no coinciden'})

        if User.objects.filter(username=username).exists():
            return render(request, 'auth/register.html', 
                        {'error': 'El usuario ya existe'})

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
            return render(request, 'auth/login.html', 
                        {'error': 'Usuario o contraseña incorrectos'})

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

    if query:
        try:
            url = f"https://api.pokemontcg.io/v2/cards"
            api_key = os.getenv('POKEMON_TCG_API_KEY')
            headers = {'X-Api-Key': api_key}
            params = {'q': f'name:{query}'}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                cards_data = data.get('data', [])
                
                for card in cards_data[:20]:
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
                error = f"Error en la API: {response.status_code}"
        
        except Exception as e:
            error = f"Error conectando con la API: {str(e)}"
    else:
        # Si no hay búsqueda, mostrar cartas más buscadas (con más alertas)
        top_cards = Card.objects.annotate(
            alert_count=Count('alerts')
        ).filter(alert_count__gt=0).order_by('-alert_count')[:8]
        
        api_key = os.getenv('POKEMON_TCG_API_KEY')
        
        for card in top_cards:
            market_price = 'N/A'
            
            # Consultar la API para obtener el precio actual
            try:
                url = f"https://api.pokemontcg.io/v2/cards/{card.pokemontcg_id}"
                headers = {'X-Api-Key': api_key}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    api_data = response.json().get('data', {})
                    tcgplayer_prices = api_data.get('tcgplayer', {}).get('prices', {})
                    
                    if 'holofoil' in tcgplayer_prices:
                        market_price = tcgplayer_prices['holofoil'].get('market')
                    elif 'normal' in tcgplayer_prices:
                        market_price = tcgplayer_prices['normal'].get('market')
                    
                    market_price = market_price or 'N/A'
            except Exception as e:
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

    return render(request, 'search.html', {
        'query': query,
        'results': results,
        'error': error,
        'is_popular': not query and results
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
        # Validar y crear la alerta usando el serializador
        serializer_data = {
            'pokemontcg_id': pokemontcg_id,
            'discount_percentage': int(discount_percentage)
        }
        
        # Crear un request fake para el contexto del serializador
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
            # Extraer el primer error
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