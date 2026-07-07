# PokéAlert - Sistema de Alertas de Precios Pokémon TCG

Sistema Django completo para monitorear y alertar cambios de precios en cartas del Pokémon Trading Card Game (TCG).

## Características

- **Búsqueda avanzada de cartas**: Filtro por rarezas, tipos, artistas, especies Pokémon
- **Sistema de alertas**: Configura alertas por descuento porcentual o precio objetivo
- **Histórico de precios**: Gráficos interactivos de evolución de precios
- **API REST**: Endpoints para integrar con aplicaciones externas
- **Integración TCG**: Sincronización automática con API Pokémon TCG
- **Tareas periódicas**: Celery + Beat para actualización automática de precios
- **Caché optimizado**: Redis para búsquedas y detalles rápidos

## Requisitos

- Python 3.10+
- PostgreSQL 12+
- Redis 6+
- pip (gestor de paquetes Python)

## Instalación Rápida

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/pokealert.git
cd pokealert
```

### 2. Crear entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
# Dependencias de producción
pip install -r requirements.txt

# Dependencias de desarrollo (opcional)
pip install -r requirements-dev.txt
```

### 4. Configurar variables de entorno

```bash
# Crear archivo .env (copiar desde .env.example si existe)
cp .env.example .env
# Editar .env con tus configuraciones:
# - SECRET_KEY (generar con: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
# - DATABASE_URL
# - REDIS_URL
# - DEBUG
```

### 5. Inicializar base de datos

```bash
# Aplicar migraciones
python manage.py migrate

# Cargar datos iniciales (si aplica)
python manage.py populate_relations

# Crear superusuario
python manage.py createsuperuser
```

### 6. Descargar cartas (datos iniciales)

```bash
python manage.py descargar_cartas_json
```

### 7. Ejecutar servidor de desarrollo

```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery Worker (en otra terminal)
celery -A config worker -l info

# Terminal 3: Celery Beat (en otra terminal, opcional)
celery -A config beat -l info
```

Accede a: http://localhost:8000

## Estructura del Proyecto

```
pokealert/
├── cards/                  # App principal de cartas
│   ├── models.py          # Modelos Card, Rarity, Supertype, etc
│   ├── views.py           # Vistas de búsqueda y detalles
│   ├── serializers.py     # Serializadores REST
│   ├── services/          # Lógica de negocio
│   │   ├── pokemontcg_service.py  # Cliente API Pokémon TCG
│   │   ├── pricing.py      # Extracción de precios
│   │   └── card_formatter.py      # Formateo de datos
│   └── management/commands/  # Comandos customizados
│       └── descargar_cartas_json.py
├── alerts/                # App de alertas de precio
│   ├── models.py         # PriceAlert, PriceHistory
│   ├── serializers.py    # API de alertas
│   └── views.py          # Viewsets REST
├── tasks/                # Tareas Celery
│   ├── tasks.py         # check_pokemon_prices, actualizar_pokedex_automatica
│   └── views.py         # Vistas relacionadas a tareas
├── users/               # App de autenticación y perfiles
│   ├── models.py        # Perfil de usuario
│   ├── views.py         # Vista de perfil
│   └── forms.py         # Formularios de usuario
├── config/              # Configuración del proyecto
│   ├── settings.py      # Settings Django
│   ├── celery.py        # Configuración Celery
│   └── urls.py          # URLs principales
├── templates/           # Plantillas HTML
├── static/              # CSS, JS, imágenes
├── tests/               # Suite de tests
├── docs/                # Documentación
│   ├── PROJECT_DOCUMENTATION.md
│   ├── CELERY.md
│   └── CODE_QUALITY.md
├── requirements.txt     # Dependencias de producción
├── requirements-dev.txt # Dependencias de desarrollo
├── pyproject.toml       # Configuración (Black, pytest, etc)
├── .flake8              # Configuración Flake8
└── validate.py          # Script de validación

```

## Desarrollo

### Validación de Código

Antes de hacer commit, ejecuta:

```bash
# Validación completa
python validate.py

# O ejecutar herramientas por separado:
black cards alerts tasks users config tests  # Formateador
flake8 cards alerts tasks users config       # Linter
pydocstyle cards alerts tasks users config   # Validador de docstrings
pytest                                        # Tests
```

Ver [docs/CODE_QUALITY.md](docs/CODE_QUALITY.md) para más detalles.

### Tests

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=cards --cov=alerts --cov=tasks --cov=users --cov-report=html

# Tests específicos
pytest tests/test_models.py -v
pytest tests/test_apis.py::test_alert_list_api -v
```

### Documentación del Código

Todos los módulos, clases y funciones deben tener docstrings en formato Google:

```python
def fetch_card(card_id: str) -> dict:
    """Obtiene datos de una carta desde la API Pokémon TCG.
    
    Args:
        card_id: ID único de la carta en formato TCG.
    
    Returns:
        Diccionario con datos de la carta.
    
    Raises:
        requests.RequestException: Si la API no responde.
    """
```

## API REST

### Endpoints principales

```
GET    /api/cards/                  # Listar cartas (con filtros)
GET    /api/cards/{id}/             # Detalle de carta
GET    /api/cards/{id}/price-history/  # Histórico de precios
POST   /api/alerts/                 # Crear alerta
GET    /api/alerts/                 # Listar alertas del usuario
PUT    /api/alerts/{id}/            # Actualizar alerta
DELETE /api/alerts/{id}/            # Eliminar alerta
GET    /api/search/suggestions/     # Autocompletado de búsqueda
```

Documentación interactiva: http://localhost:8000/api/docs/ (Swagger UI)

## Tareas Periódicas (Celery)

### check_pokemon_prices (cada 6 horas)
- Obtiene precios actuales del Pokémon TCG
- Compara con alertas configuradas
- Envía notificaciones

### actualizar_pokedex_automatica (diariamente)
- Sincroniza datos de especies Pokémon
- Actualiza atributos TCG (rarezas, tipos, etc)

Ver [docs/CELERY.md](docs/CELERY.md) para configuración completa.

## Problemas Comunes

### "ModuleNotFoundError: No module named 'django'"
```bash
# Asegúrate de que el venv esté activado
# En Windows: venv\Scripts\activate
# En Linux/Mac: source venv/bin/activate
# Luego: pip install -r requirements.txt
```

### "ConnectionError: Error -2 connecting to localhost:6379"
```bash
# Redis no está ejecutándose. Inicia Redis:
# Windows: redis-server (si está instalado)
# Docker: docker run -d -p 6379:6379 redis:latest
```

### "ProgrammingError: relation 'cards_card' does not exist"
```bash
python manage.py migrate
python manage.py descargar_cartas_json
```

## Contribuir

1. Crea una rama feature: `git checkout -b feature/nueva-funcionalidad`
2. Realiza cambios y tests
3. Ejecuta validación: `python validate.py`
4. Commit: `git commit -am "Agrega nueva funcionalidad"`
5. Push: `git push origin feature/nueva-funcionalidad`
6. Abre Pull Request

## Licencia

MIT - Ver LICENSE para detalles.

## Contacto

Para preguntas o sugerencias, abre un issue en GitHub.

---

**Última actualización**: Julio 2026  
**Versión**: 1.0.0  
**Estado**: Desarrollo activo
