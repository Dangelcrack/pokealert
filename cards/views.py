"""Vistas y utilidades principales de la aplicación `cards`.

Este módulo combina helpers de búsqueda, normalización, sincronización con la API,
views frontend y endpoints de API REST para cartas y alertas."""

from datetime import timedelta

from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.utils import timezone


from rest_framework import viewsets

from cards.services.pokemontcg_service import fetch_cards
from alerts.models import PriceAlert, PriceHistory
from cards.services.pricing_trends import obtener_top_movimientos
from cards.services.card_formatter import format_card
from cards.services.text_utils import get_expanded_search_terms
from cards.services.catalog_service import get_filter_options
from cards.services.card_detail_service import obtener_contexto_card_detail
from alerts.services import (
    crear_alerta,
    actualizar_descuento_alerta,
    AlertaSinPrecioValidoError,
    CartaNoEncontradaError,
)
from cards.services.search_service import buscar_cartas, build_search_query
from .models import Card
from .serializers import CardSerializer

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
    """Gestión de la búsqueda de cartas combinando DB local, JSON y API externa."""
    query_raw = request.GET.get("q", "").strip()
    selected_sort = request.GET.get("sort", "")
    selected_supertype_id = request.GET.get("supertype", "")
    selected_rarity_id = request.GET.get("rarity", "")
    selected_subtype_id = request.GET.get("subtype", "")
    selected_artist_id = request.GET.get("artist", "")

    page_param = request.GET.get("page")
    current_page = max(1, int(page_param) if page_param and page_param.isdigit() else 1)

    busqueda = buscar_cartas(
        query_raw=query_raw,
        selected_sort=selected_sort,
        rarity_id=selected_rarity_id,
        supertype_id=selected_supertype_id,
        subtype_id=selected_subtype_id,
        artist_id=selected_artist_id,
        current_page=current_page,
    )

    context = {
        "results": busqueda["results"],
        "error": None,
        "current_page": current_page,
        "total_pages": busqueda["total_pages"],
        "has_next": busqueda["has_next"],
        "has_previous": busqueda["has_previous"],
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
def card_detail(request, card_id):
    """Renderiza el detalle de una carta Pokémon TCG."""
    context = obtener_contexto_card_detail(card_id)
    return render(request, "card_detail.html", context)


@login_required(login_url="login")
@require_POST
def create_alert(request):
    """Crea una alerta de precio para la carta indicada por el usuario."""
    try:
        alerta = crear_alerta(
            user=request.user,
            pokemontcg_id=request.POST.get("pokemontcg_id"),
            discount_percentage=request.POST.get("discount_percentage"),
            current_price_str=request.POST.get("current_price"),
        )
        messages.success(request, f"Alerta creada para ${alerta.target_price}.")
        return redirect("dashboard")
    except (AlertaSinPrecioValidoError, CartaNoEncontradaError) as e:
        messages.error(request, str(e))
        return redirect("search")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect("search")


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def edit_alert(request, alert_id):
    """Permite editar el porcentaje de descuento de una alerta existente."""
    alert = get_object_or_404(PriceAlert, id=alert_id, user=request.user)
    historial = PriceHistory.objects.filter(card=alert.card).order_by("recorded_at")

    if request.method == "POST":
        actualizar_descuento_alerta(alert, request.POST.get("discount_percentage"))
        messages.success(request, "Alerta y precio objetivo actualizados correctamente.")
        return redirect("dashboard")

    context = {
        "alert": alert,
        "price_dates": [h.recorded_at.strftime("%Y-%m-%d") for h in historial],
        "price_values": [float(h.price) for h in historial],
    }
    return render(request, "alerts/edit_alert.html", context)


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
    en los últimos 30 días, calculado a partir de PriceHistory."""
    top_subidas, top_bajadas = obtener_top_movimientos(dias=30, top_n=5)

    contexto = {
        "total_cartas": Card.objects.count(),
        "top_subidas": top_subidas,
        "top_bajadas": top_bajadas,
    }
    return render(request, "market_trends.html", contexto)
