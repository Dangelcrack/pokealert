"""API REST relacionadas con `alerts`.

Incluye viewsets para gestión de `PriceAlert` y lectura de
`PriceHistory`.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import PriceAlert, PriceHistory
from .serializers import PriceAlertSerializer, PriceHistorySerializer


@extend_schema_view(
    list=extend_schema(
        summary="Listar mis alertas",
        description="Devuelve las alertas de precio del usuario autenticado, más recientes primero.",
    ),
    retrieve=extend_schema(summary="Detalle de una alerta"),
    create=extend_schema(
        summary="Crear alerta de precio",
        description=(
            "Crea una alerta para la carta indicada. Consulta el precio de mercado "
            "actual en la API de Pokémon TCG en el momento de la creación (no usa "
            "un precio cacheado) y calcula `target_price` a partir de "
            "`discount_percentage`. Falla con 400 si ya existe una alerta del "
            "usuario para esa carta, o si la carta no tiene precio de mercado disponible."
        ),
    ),
    update=extend_schema(summary="Actualizar alerta (reemplazo completo)"),
    partial_update=extend_schema(summary="Actualizar alerta (parcial)"),
    destroy=extend_schema(summary="Eliminar alerta"),
)
class PriceAlertViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD de `PriceAlert` del usuario autenticado.

    Proporciona las operaciones estándar y restringe el queryset al
    usuario que realiza la petición (privacidad de datos).
    """

    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]
    queryset = PriceAlert.objects.none()  # usado por drf-spectacular al generar el schema

    def get_queryset(self):
        """Devuelve las alertas del usuario autenticado.

        Restringe el queryset a `self.request.user` para privacidad.
        Durante la generación del schema de OpenAPI no hay un usuario
        real, así que se devuelve un queryset vacío en ese caso.
        """
        if getattr(self, "swagger_fake_view", False):
            return PriceAlert.objects.none()
        return PriceAlert.objects.filter(user=self.request.user).order_by("-id")


@extend_schema_view(
    list=extend_schema(
        summary="Listar histórico de precios",
        description="Devuelve puntos de histórico de precios, opcionalmente filtrados por carta.",
        parameters=[
            OpenApiParameter(
                name="card_id",
                description="ID de la carta (pokemontcg_id) para filtrar el histórico.",
                required=False,
                type=str,
            ),
        ],
    ),
    retrieve=extend_schema(summary="Detalle de un punto de histórico"),
)
class PriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet solo-lectura para `PriceHistory`.

    Permite listar/filtrar el histórico de una carta determinada usando
    el parámetro `card_id` en la query string.

    Nota: este endpoint no requiere autenticación (el histórico de precios
    se considera dato público de mercado).
    """

    serializer_class = PriceHistorySerializer
    queryset = PriceHistory.objects.all()

    def get_queryset(self):
        """Si se pasa `card_id` como query param, filtra por esa carta; en caso
        contrario devuelve todo el histórico."""
        card_id = self.request.query_params.get("card_id")
        if card_id:
            return PriceHistory.objects.filter(card_id=card_id).order_by("-id")
        return PriceHistory.objects.all().order_by("-id")
