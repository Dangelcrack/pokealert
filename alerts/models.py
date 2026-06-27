from django.db import models
from django.contrib.auth.models import User
from cards.models import Card

class PriceAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='alerts')
    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.card.name} ({self.discount_percentage}%)"
    
    class Meta:
        unique_together = ['user', 'card'] 

class PriceHistory(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    marketplace = models.CharField(max_length=100, default='tcgplayer')
    
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.card.name} - ${self.price}"
    
    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['card', 'recorded_at']), 
        ]