"""
Guía de Calidad de Código - PokéAlert

Este documento describe las herramientas de calidad de código y las convenciones
utilizadas en el proyecto PokéAlert.

## Herramientas de Análisis

### Black
Formateador de código Python automático que asegura consistencia visual.
- Línea máxima: 100 caracteres (configurado en pyproject.toml)
- Se ejecuta automáticamente durante el desarrollo

### Flake8
Linter que verifica errores de sintaxis, estilo y complejidad.
- Configuración: .flake8
- Ignora: E501 (líneas largas, manejadas por Black), E203 (espacios en blanco)
- Excluye: migrations/, venv/, .git/

### Pydocstyle
Validador de docstrings con convención Google.
- Todos los módulos, clases, funciones públicas deben tener docstrings
- Formato: Google style (encabezado + descripción)
- Ejemplos de docstrings profesionales:

```python
def fetch_card(card_id: str) -> dict:
    """Obtiene datos de una carta desde la API Pokémon TCG.
    
    Args:
        card_id: ID único de la carta en el formato TCG.
    
    Returns:
        Diccionario con datos de la carta (nombre, imagen, precio, etc).
    
    Raises:
        requests.RequestException: Si la API no responde.
        ValueError: Si el card_id es inválido.
    """
```

### Pytest + Coverage
Suite de pruebas con cobertura automática.
- Ubicación: tests/
- Comando: pytest (o python manage.py test)
- Objetivo: >70% cobertura de código

## Convenciones de Código

### Nombrado
- Módulos: snake_case (card_formatter.py)
- Clases: PascalCase (CardSerializer)
- Funciones/métodos: snake_case (fetch_cards)
- Constantes: UPPER_CASE (POKEMONTCG_API_URL)

### Imports
- Orden: stdlib, third-party, local
- Usar isort para organizar automáticamente
- Evitar import * (importar símbolos explícitamente)

### Docstrings
Todos los módulos, clases y funciones públicas requieren docstrings.

**Módulo:**
```python
"""Descripción breve del propósito del módulo.

Descripción más detallada si es necesario, incluyendo casos de uso
y detalles de implementación relevantes.
"""
```

**Función:**
```python
def fetch_cards(query: str, limit: int = 10) -> list:
    """Busca cartas en la API Pokémon TCG.
    
    Args:
        query: Término de búsqueda (nombre de carta).
        limit: Número máximo de resultados (por defecto 10).
    
    Returns:
        Lista de diccionarios con datos de cartas.
    
    Raises:
        requests.RequestException: Si la API falla.
    """
```

**Clase:**
```python
class Card(models.Model):
    """Modelo de una carta del Pokémon TCG.
    
    Almacena información de las cartas, incluyendo metadatos TCG,
    imágenes, y relaciones a atributos de referencia (rareza, tipo, etc).
    """
```

## Flujo de Desarrollo

1. **Escribir código** - Seguir convenciones de nombrado y docstrings
2. **Formatear** - Ejecutar `black .` antes de commit
3. **Validar** - Ejecutar `flake8` y `pydocstyle` para verificar estilo
4. **Probar** - Ejecutar `pytest` y verificar cobertura >70%
5. **Commit** - Git commit con mensaje claro

## Comandos Útiles

```bash
# Formatear todo el código
black cards alerts tasks users config tests

# Validar estilo
flake8 cards alerts tasks users config tests
pydocstyle cards alerts tasks users config tests

# Ejecutar tests
pytest
pytest --cov  # Con cobertura

# Limpiar archivos de cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

## Configuración

- **pyproject.toml**: Configuración centralizada para Black, isort, pytest, coverage
- **.flake8**: Configuración específica de Flake8
- **pytest.ini**: Configuración de Pytest (también en pyproject.toml)

## Mejoras Futuras

1. Pre-commit hooks (validar antes de commit)
2. CI/CD pipeline (GitHub Actions / GitLab CI)
3. Type checking (mypy)
4. Seguridad (bandit)
5. Complejidad (radon)
"""
