from django.contrib import admin
from .models import PriceAlert, PriceHistory

@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'card', 'target_price', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'card__name')

@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('card', 'price', 'source', 'recorded_at')
    list_filter = ('source',)
    search_fields = ('card__name',)