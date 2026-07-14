"""Tests para cards/services/text_utils.py."""

import pytest

from cards.services.text_utils import get_expanded_search_terms, normalize


def test_normalize_quita_acentos_y_pasa_a_minusculas():
    """Normalize debe quitar acentos y convertir a minúsculas."""
    assert normalize("Pikachú") == "pikachu"
    assert normalize("CHARIZARD") == "charizard"
    assert normalize("  Ñandú  ") == "nandu"


def test_normalize_con_entrada_vacia_devuelve_cadena_vacia():
    """Normalize debe manejar None y cadenas vacías sin lanzar excepción."""
    assert normalize("") == ""
    assert normalize(None) == ""


def test_normalize_es_idempotente():
    """Normalizar dos veces debe dar el mismo resultado que una vez."""
    texto = "Électrode"
    assert normalize(normalize(texto)) == normalize(texto)


def test_expanded_terms_incluye_termino_original():
    """El conjunto expandido siempre debe incluir el término original en
    minúsculas."""
    terms = get_expanded_search_terms("Pikachu")
    assert "pikachu" in terms


def test_expanded_terms_con_query_vacia_devuelve_set_vacio():
    """Una query vacía no debe generar términos expandidos."""
    assert get_expanded_search_terms("") == set()
    assert get_expanded_search_terms(None) == set()


@pytest.mark.django_db
def test_expanded_terms_devuelve_un_set():
    """El resultado siempre debe ser un set (sin duplicados),
    independientemente de cuántas coincidencias haya en los diccionarios de
    traducción."""
    terms = get_expanded_search_terms("cualquier termino raro que no tenga traduccion")
    assert isinstance(terms, set)
