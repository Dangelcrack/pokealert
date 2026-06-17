from django.contrib import admin
from .models import Card

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('name', 'pokemontcg_id', 'rarity', 'created_at')
    list_filter = ('rarity',)
    search_fields = ('name', 'pokemontcg_id')