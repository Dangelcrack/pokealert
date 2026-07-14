"""Tests para cards/services/pricing_trends.py."""

from datetime import timedelta

import pytest
from django.utils import timezone

from cards.models import Card
from cards.services.pricing_trends import calcular_variaciones_precio, obtener_top_movimientos


def _crear_carta_con_historial(pokemontcg_id, precio_actual, precio_hace_dias, dias_atras):
    """Crea una Card con un punto de PriceHistory retrasado `dias_atras` días.

    `recorded_at` es auto_now_add, así que se crea primero y se retrasa
    después con un `update()` directo sobre el queryset.
    """
    from alerts.models import PriceHistory

    card = Card.objects.create(
        pokemontcg_id=pokemontcg_id,
        name=pokemontcg_id,
        image_url="https://example.com/img.png",
        price=precio_actual,
    )
    history = PriceHistory.objects.create(card=card, price=precio_hace_dias)
    fecha_pasada = timezone.now() - timedelta(days=dias_atras)
    PriceHistory.objects.filter(id=history.id).update(recorded_at=fecha_pasada)
    return card


@pytest.mark.django_db
def test_variacion_positiva_va_solo_en_subidas():
    """Una carta que sube de precio debe aparecer solo en top_subidas."""
    _crear_carta_con_historial(
        "wartortle-up", precio_actual=10.0, precio_hace_dias=5.0, dias_atras=5
    )

    top_subidas, top_bajadas = obtener_top_movimientos(dias=30, top_n=5)

    assert len(top_subidas) == 1
    assert top_subidas[0]["carta"].pokemontcg_id == "wartortle-up"
    assert top_subidas[0]["variacion"] > 0
    assert top_bajadas == []


@pytest.mark.django_db
def test_variacion_negativa_va_solo_en_bajadas():
    """Una carta que baja de precio debe aparecer solo en top_bajadas, nunca en
    top_subidas.

    Este es el bug de Wartortle que arreglamos manualmente antes: una bajada
    no debe colarse en la lista de subidas para 'rellenar' el top 5.
    """
    _crear_carta_con_historial(
        "wartortle-down", precio_actual=8.0, precio_hace_dias=10.0, dias_atras=5
    )

    top_subidas, top_bajadas = obtener_top_movimientos(dias=30, top_n=5)

    assert top_subidas == []
    assert len(top_bajadas) == 1
    assert top_bajadas[0]["carta"].pokemontcg_id == "wartortle-down"
    assert top_bajadas[0]["variacion"] < 0


@pytest.mark.django_db
def test_variacion_cero_se_excluye():
    """Una carta sin cambio de precio no debe aparecer en ninguna de las dos
    listas."""
    _crear_carta_con_historial(
        "sin-cambio", precio_actual=10.0, precio_hace_dias=10.0, dias_atras=5
    )

    variaciones = calcular_variaciones_precio(dias=30)

    assert variaciones == []


@pytest.mark.django_db
def test_historial_fuera_de_ventana_se_ignora():
    """Un punto de histórico más antiguo que la ventana de días no debe
    contar."""
    _crear_carta_con_historial(
        "historico-viejo", precio_actual=20.0, precio_hace_dias=5.0, dias_atras=60
    )

    variaciones = calcular_variaciones_precio(dias=30)

    assert variaciones == []


@pytest.mark.django_db
def test_carta_sin_precio_se_excluye():
    """Cartas con price=None no deben entrar en el cálculo
    (Card.objects.exclude(price__isnull=True))."""
    Card.objects.create(
        pokemontcg_id="sin-precio",
        name="Sin Precio",
        image_url="https://example.com/img.png",
        price=None,
    )

    variaciones = calcular_variaciones_precio(dias=30)

    assert variaciones == []


@pytest.mark.django_db
def test_top_n_limita_resultados():
    """`top_n` debe limitar cuántas cartas se devuelven en cada lista."""
    for i in range(7):
        _crear_carta_con_historial(
            f"subida-{i}", precio_actual=10.0 + i, precio_hace_dias=5.0, dias_atras=3
        )

    top_subidas, _ = obtener_top_movimientos(dias=30, top_n=3)

    assert len(top_subidas) == 3
