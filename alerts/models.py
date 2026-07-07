"""Modelos relacionados con alertas y histórico de precios.

`PriceAlert` almacena alertas de usuario; `PriceHistory` registra el precio
diario de una carta en un marketplace."""

from django.db import models
from django.contrib.auth.models import User
from cards.models import Card


class PriceAlert(models.Model):
    """Almacena una alerta de precio creada por un usuario para una carta.

    Los usuarios pueden establecer un precio objetivo o un porcentaje de descuento
    para recibir notificaciones cuando la carta alcance el criterio."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alerts")
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="alerts")
    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Representación breve de la alerta mostrando usuario, carta y porcentaje."""
        return f"{self.user.username} - {self.card.name} ({self.discount_percentage}%)"

    class Meta:
        """Restricciones e índices para `PriceAlert`."""

        unique_together = ["user", "card"]


class PriceHistory(models.Model):
    """Registra el histórico diario de precios para una carta en el marketplace.

    Cada instancia guarda un punto de precio asociado a una carta y su marca temporal."""

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="price_history")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    marketplace = models.CharField(max_length=100, default="tcgplayer")

    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Representación corta del punto de histórico: carta y precio."""
        return f"{self.card.name} - ${self.price}"

    class Meta:
        """Configuración de orden y índices para consultas de `PriceHistory`."""

        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["card", "recorded_at"]),
        ]
