from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from cards.views import (
    CardViewSet,
    edit_alert, 
    home,
    register,
    search_suggestions, 
    user_login, 
    user_logout, 
    dashboard, 
    search,
    test_pokemon_api,
    create_alert,
    card_detail
)
from alerts.views import PriceAlertViewSet, PriceHistoryViewSet
from tasks import views

router = DefaultRouter()
router.register(r'cards', CardViewSet)
router.register(r'alerts', PriceAlertViewSet, basename='alert')
router.register(r'price-history', PriceHistoryViewSet, basename='price-history')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API REST
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('api/test-pokemon/', test_pokemon_api),
    
    # Frontend
    path('', home, name='home'),
    path('register/', register, name='register'),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('search/', search, name='search'),
    path('create-alert/', create_alert, name='create_alert'),
    path('search-suggestions/', search_suggestions, name='search_suggestions'),
    path('card/<slug:card_name>/', card_detail, name='card_detail'),
    path('alerts/edit/<int:alert_id>/', edit_alert, name='edit_alert'),
]