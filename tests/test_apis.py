import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from alerts.models import PriceAlert
from cards.models import Card


@pytest.mark.django_db
def test_alert_list_api():
    user = User.objects.create_user(
        username='testuser',
        password='password'
    )

    card = Card.objects.create(
        name='Pikachu V',
        pokemontcg_id='base1-1',
        image_url='https://example.com/pika.jpg'
    )

    PriceAlert.objects.create(
        user=user,
        card=card,
        target_price=10.0
    )

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse('alert-list')
    response = client.get(url)

    assert response.status_code == 200