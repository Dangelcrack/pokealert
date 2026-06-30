import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from alerts.models import PriceAlert, PriceHistory
from cards.models import Card


@pytest.fixture
def setup_data(db):
    """Fixture para crear datos básicos de prueba."""
    user = User.objects.create_user(
        username='testuser',
        password='password'
    )

    card = Card.objects.create(
        name='Pikachu V',
        pokemontcg_id='base1-1',
        image_url='https://example.com/pikachu.jpg'
    )

    return user, card


@pytest.mark.django_db
def test_price_alert_creation(setup_data):
    user, card = setup_data

    alert = PriceAlert.objects.create(
        user=user,
        card=card,
        target_price=10.50,
        discount_percentage=20
    )

    assert alert.user.username == 'testuser'
    assert alert.card.name == 'Pikachu V'
    assert alert.is_active is True
    assert str(alert) == "testuser - Pikachu V (20%)"


@pytest.mark.django_db
def test_unique_together_constraint(setup_data):
    """Verifica que un usuario no pueda tener dos alertas para la misma carta."""
    user, card = setup_data

    PriceAlert.objects.create(
        user=user,
        card=card,
        discount_percentage=10
    )

    with pytest.raises(IntegrityError):
        PriceAlert.objects.create(
            user=user,
            card=card,
            discount_percentage=50
        )


@pytest.mark.django_db
def test_price_history_creation(setup_data):
    _, card = setup_data

    history = PriceHistory.objects.create(
        card=card,
        price=15.99,
        marketplace='tcgplayer'
    )

    assert history.price == 15.99
    assert history.card.name == 'Pikachu V'
    assert history.marketplace == 'tcgplayer'