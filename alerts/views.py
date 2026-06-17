from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import PriceAlert, PriceHistory
from .serializers import PriceAlertSerializer, PriceHistorySerializer

class PriceAlertViewSet(viewsets.ModelViewSet):
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PriceAlert.objects.filter(user=self.request.user)

class PriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PriceHistorySerializer
    
    def get_queryset(self):
        card_id = self.request.query_params.get('card_id')
        if card_id:
            return PriceHistory.objects.filter(card_id=card_id)
        return PriceHistory.objects.all()