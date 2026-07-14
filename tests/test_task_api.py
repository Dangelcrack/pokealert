"""Pruebas de los endpoints protegidos del módulo tasks."""

from unittest.mock import MagicMock, patch

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
def test_check_prices_valid_token_lanza_hilo_en_background(client, monkeypatch):
    """Con token válido debe lanzar un hilo con check_pokemon_prices y
    responder de inmediato con status 'started', sin esperar a que el hilo
    termine."""
    monkeypatch.setenv("CRON_SECRET_TOKEN", "mi-token")

    with patch("tasks.views.threading.Thread") as mock_thread_class:
        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance

        response = client.get(
            reverse("trigger_check_prices"),
            {"token": "mi-token"},
        )

        # Se creó un hilo apuntando a check_pokemon_prices...
        from tasks.tasks import check_pokemon_prices

        mock_thread_class.assert_called_once_with(target=check_pokemon_prices)
        # ...y se arrancó
        mock_thread_instance.start.assert_called_once()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert "message" in data


@pytest.mark.django_db
def test_check_prices_valid_token_responde_500_si_thread_falla(client, monkeypatch):
    """Si threading.Thread lanza una excepción al crearse, debe devolver
    500."""
    monkeypatch.setenv("CRON_SECRET_TOKEN", "mi-token")

    with patch("tasks.views.threading.Thread", side_effect=RuntimeError("boom")):
        response = client.get(
            reverse("trigger_check_prices"),
            {"token": "mi-token"},
        )

    assert response.status_code == 500
    assert response.json()["status"] == "error"
