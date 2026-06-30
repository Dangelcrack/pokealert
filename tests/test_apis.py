import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser',
        password='password'
    )


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_alert_list_api(auth_client):
    url = reverse('alert-list')
    response = auth_client.get(url)

    assert response.status_code == 200