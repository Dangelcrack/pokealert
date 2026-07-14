import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User


# 1. Configuración global: Forzar el caché en memoria
@pytest.fixture(autouse=True)
def use_locmem_cache(settings):
    """Sobrescribe el backend de caché para usar memoria RAM.

    El argumento 'settings' es el fixture proporcionado por pytest-
    django.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


# 2. Fixtures de Autenticación y Cliente
@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="testuser", password="password123")


@pytest.fixture
def auth_client(api_client, test_user):
    api_client.force_authenticate(user=test_user)
    return api_client
