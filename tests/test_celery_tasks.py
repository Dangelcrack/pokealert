"""Pruebas de comandos y tareas Celery para la lógica de alertas y sincronización."""

import pytest
from django.core.management import call_command
from django.contrib.auth.models import User
from cards.models import Card
from alerts.models import PriceAlert


@pytest.fixture
def setup_data(db):
    """Fixture para preparar los datos que necesita el comando."""
    user = User.objects.create_user(username="testuser", password="password")

    card = Card.objects.create(name="Pikachu V", pokemontcg_id="base1-1")

    PriceAlert.objects.create(user=user, card=card, target_price=10.00)

    return user, card


@pytest.mark.django_db
def test_check_prices_command(setup_data):
    """Ejecuta el comando check_prices y verifica que no falle."""

    try:
        call_command("check_prices")
    except Exception as e:
        pytest.fail(f"El comando check_prices falló con error: {e}")

    assert True
