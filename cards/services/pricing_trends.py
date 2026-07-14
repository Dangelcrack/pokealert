"""Servicio de cálculo de tendencias de mercado.

Aísla la lógica de negocio de `market_trends` (comparación de precios
actuales contra el histórico) para que sea testeable sin necesidad de
simular un request HTTP.
"""

from datetime import timedelta

from django.utils import timezone

from alerts.models import PriceHistory
from cards.models import Card


def calcular_variaciones_precio(dias: int = 30) -> list[dict]:
    """Calcula la variación porcentual de precio de cada carta en el rango
    dado.

    Parámetros:
    - dias: ventana de días hacia atrás para buscar el precio de referencia.

    Devuelve una lista de dicts con `carta`, `precio_actual` y `variacion`
    (redondeada a 1 decimal), excluyendo cartas sin variación (0%) o sin
    histórico suficiente en el rango.
    """
    fecha_limite = timezone.now() - timedelta(days=dias)
    cartas_con_historial = []

    cartas = Card.objects.exclude(price__isnull=True)

    for carta in cartas:
        precio_antiguo = (
            PriceHistory.objects.filter(card=carta, recorded_at__gte=fecha_limite)
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

    return [c for c in cartas_con_historial if c["variacion"] != 0]


def obtener_top_movimientos(dias: int = 30, top_n: int = 5) -> tuple[list[dict], list[dict]]:
    """Devuelve las cartas con mayores subidas y mayores bajadas de precio.

    Parámetros:
    - dias: ventana de días para calcular la variación.
    - top_n: cuántas cartas devolver en cada lista.

    Devuelve una tupla `(top_subidas, top_bajadas)`. Cada lista contiene
    solo cartas con variación positiva o negativa respectivamente — nunca
    se mezclan, y si no hay suficientes, la lista sale corta en vez de
    rellenarse con el signo contrario.
    """
    cartas_con_historial = calcular_variaciones_precio(dias=dias)

    subidas = [c for c in cartas_con_historial if c["variacion"] > 0]
    bajadas = [c for c in cartas_con_historial if c["variacion"] < 0]

    top_subidas = sorted(subidas, key=lambda x: x["variacion"], reverse=True)[:top_n]
    top_bajadas = sorted(bajadas, key=lambda x: x["variacion"])[:top_n]

    return top_subidas, top_bajadas
