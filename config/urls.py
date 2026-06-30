from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from cards.views import (
    CardViewSet,
    card_price_history,
    delete_alert,
    edit_alert, 
    home,
    register,
    search_suggestions, 
    user_login, 
    user_logout, 
    dashboard, 
    search,
    create_alert,
    card_detail
)
from alerts.views import PriceAlertViewSet, PriceHistoryViewSet

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
    
    # Frontend
    path('', home, name='home'),
    path('register/', register, name='register'),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('search/', search, name='search'),
    path('create-alert/', create_alert, name='create_alert'),
    path('search-suggestions/', search_suggestions, name='search_suggestions'),
    path('card/<str:card_id>/', card_detail, name='card_detail'),
    path('alerts/edit/<int:alert_id>/', edit_alert, name='edit_alert'),
    path('alerts/delete/<int:alert_id>/', delete_alert, name='delete_alert'),
    path('api/card/<str:card_id>/price-history/', card_price_history, name='card_price_history'),
]