"""Pruebas de los endpoints protegidos del módulo tasks."""

from unittest.mock import patch

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_check_prices_without_token(client, monkeypatch):
    """Debe devolver 403 cuando no se proporciona el token."""

    monkeypatch.setenv("CRON_SECRET_TOKEN", "mi-token")

    response = client.get(reverse("trigger_check_prices"))

    assert response.status_code == 403
    assert response.json() == {"error": "No autorizado"}


@pytest.mark.django_db
def test_check_prices_invalid_token(client, monkeypatch):
    """Debe devolver 403 cuando el token es incorrecto."""

    monkeypatch.setenv("CRON_SECRET_TOKEN", "mi-token")

    response = client.get(
        reverse("trigger_check_prices"),
        {"token": "token-invalido"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": "No autorizado"}


@pytest.mark.django_db
@patch("tasks.views.check_pokemon_prices")
def test_check_prices_valid_token(mock_check_prices, client, monkeypatch):
    """Debe ejecutar la tarea y devolver 200 cuando el token es válido."""

    monkeypatch.setenv("CRON_SECRET_TOKEN", "mi-token")

    mock_check_prices.return_value = {
        "processed": 5,
        "updated": 2,
    }

    response = client.get(
        reverse("trigger_check_prices"),
        {"token": "mi-token"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["resultado"] == {
        "processed": 5,
        "updated": 2,
    }

    mock_check_prices.assert_called_once()
