"""Administración de Django para el modelo de cartas."""

from django.contrib import admin
from .models import Card


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    """Configuración del admin para `Card`.

    Presenta columnas relevantes y permite búsquedas por nombre e ID TCG."""

    list_display = ("name", "pokemontcg_id", "rarity", "created_at")
    list_filter = ("rarity",)
    search_fields = ("name", "pokemontcg_id")
