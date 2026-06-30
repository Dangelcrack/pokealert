import pytest
from django.urls import reverse
from rest_framework.test import APIClient

@pytest.fixture
def auth_client():
    return APIClient()

@pytest.mark.django_db
def test_alert_list_api(auth_client):
    url = reverse('alert-list') 
    response = auth_client.get(url)
    
    assert response.status_code == 200