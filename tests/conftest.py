import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User

@pytest.fixture
def api_client():
    """Retorna un cliente de API para hacer peticiones en los tests."""
    return APIClient()

@pytest.fixture
def test_user(db):
    """Crea un usuario estándar para usar en los tests."""
    return User.objects.create_user(username='testuser', password='password123')

@pytest.fixture
def auth_client(api_client, test_user):
    """Retorna un cliente ya autenticado."""
    api_client.force_authenticate(user=test_user)
    return api_client