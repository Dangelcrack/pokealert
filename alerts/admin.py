from django.contrib import admin
from .models import PriceAlert, PriceHistory


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ("user", "card", "target_price", "discount_percentage", "is_active")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "card__name")


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("card", "price", "marketplace", "recorded_at")
    list_filter = ("marketplace", "recorded_at")
    search_fields = ("card__name",)
    readonly_fields = ("recorded_at",)
    ordering = ["-recorded_at"]
