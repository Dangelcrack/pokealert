from django.urls import path
from tasks import views

urlpatterns = [
    path("check-prices/", views.trigger_check_prices, name="trigger_check_prices"),
    path("update-pokedex/", views.trigger_update_pokedex, name="trigger_update_pokedex"),
]
