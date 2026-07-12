"""API REST relacionadas con `alerts`.

Incluye viewsets para gestión de `PriceAlert` y lectura de `PriceHistory`."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import PriceAlert, PriceHistory
from .serializers import PriceAlertSerializer, PriceHistorySerializer


class PriceAlertViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD de `PriceAlert` del usuario autenticado.

    Proporciona las operaciones estándar y restringe el queryset al usuario
    que realiza la petición (privacidad de datos)."""

    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Devuelve las alertas del usuario autenticado.

        Restringe el queryset a `self.request.user` para privacidad."""
        return PriceAlert.objects.filter(user=self.request.user).order_by("-id")


class PriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet solo-lectura para `PriceHistory`.

    Permite listar/filtrar el histórico de una carta determinada usando
    el parámetro `card_id` en la query string."""

    serializer_class = PriceHistorySerializer

    def get_queryset(self):
        """Si se pasa `card_id` como query param, filtra por esa carta; en
        caso contrario devuelve todo el histórico."""
        card_id = self.request.query_params.get("card_id")
        if card_id:
            return PriceHistory.objects.filter(card_id=card_id).order_by("-id")
        return PriceHistory.objects.all().order_by("-id")
