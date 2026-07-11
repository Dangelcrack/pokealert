<div align="center">

# 🔔 PokéAlert

### Sistema de Alertas de Precios para Pokémon TCG

Plataforma web construida con Django para monitorizar el mercado de cartas del Pokémon Trading Card Game, con histórico de precios, alertas personalizadas y sincronización automática vía la API de Pokémon TCG.

<br>

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django)
![DRF](https://img.shields.io/badge/DRF-REST_API-A30000?style=for-the-badge&logo=django)
![Celery](https://img.shields.io/badge/Celery-Task_Queue-37814A?style=for-the-badge&logo=celery)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**[🌐 Demo en vivo](https://pokealert.onrender.com)** · **[📖 Documentación](docs/PROJECT_DOCUMENTATION.md)**

</div>

---

## 📖 Tabla de Contenidos

- [Características](#-características)
- [Tecnologías](#-tecnologías)
- [Arquitectura](#-arquitectura)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Tareas Periódicas](#-tareas-periódicas-celery)
- [API REST](#-api-rest)
- [Desarrollo y Calidad de Código](#-desarrollo-y-calidad-de-código)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Despliegue](#-despliegue)
- [Problemas Comunes](#-problemas-comunes)
- [Roadmap](#-roadmap)
- [Contribuir](#-contribuir)
- [Autor](#-autor)
- [Licencia](#-licencia)

---

## 🌟 Características

✅ Búsqueda avanzada de cartas con filtros por rareza, tipo, artista y especie Pokémon.

✅ Autocompletado de búsqueda en español con fallback a la API oficial.

✅ Sistema de alertas configurables por descuento porcentual o precio objetivo.

✅ Histórico de precios con gráficos interactivos (Chart.js).

✅ Sincronización automática con la API de Pokémon TCG.

✅ Autenticación de usuarios, incluyendo login con Google (OAuth vía django-allauth).

✅ Notificaciones por email cuando una alerta se activa.

✅ API REST documentada con Swagger para integraciones externas.

✅ Tareas periódicas con Celery + Beat para actualización de precios y datos.

✅ Suite de tests y linting automatizado (ruff, black, flake8, pydocstyle) con CI en GitHub Actions.

---

## 🚀 Tecnologías

| Tecnología | Uso |
|------------|-----|
| Python / Django | Backend y lógica de negocio |
| Django REST Framework | API REST |
| PostgreSQL | Base de datos (SQLite en despliegue de demo) |
| Celery + Redis | Tareas periódicas y caché |
| Chart.js | Visualización de histórico de precios |
| django-allauth | Autenticación y OAuth con Google |
| Tailwind CSS | Estilos de interfaz |
| Pokémon TCG API | Fuente de datos de cartas y precios |
| GitHub Actions | Integración continua (lint + tests) |
| Render | Despliegue en producción |

---

## 🏗 Arquitectura

```
Pokémon TCG API
       │
       ▼
Sincronización de cartas (management commands)
       │
       ▼
Normalización de datos (Rarity, Supertype, Subtype, Artist, Especie)
       │
       ▼
Celery Beat ──► check_pokemon_prices (cada 6h) ──► PriceHistory / Alertas
       │
       ▼
Django REST API
       │
       ▼
Frontend (Tailwind + Chart.js) / Notificaciones por email
```

El proyecto está organizado en apps Django independientes por dominio: `cards` (catálogo), `alerts` (alertas y notificaciones), `tasks` (tareas Celery) y `users` (autenticación y perfiles).

---

## 📦 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Dangelcrack/pokealert.git
cd pokealert
```

### 2. Crear entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt

# Dependencias de desarrollo (opcional)
pip install -r requirements-dev.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Genera una `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Inicializar base de datos

```bash
python manage.py migrate
python manage.py populate_relations
python manage.py createsuperuser
```

### 6. Descargar datos iniciales de cartas

```bash
python manage.py descargar_cartas_json
```

### 7. Ejecutar en desarrollo

```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery Worker
celery -A config worker -l info

# Terminal 3: Celery Beat (opcional)
celery -A config beat -l info
```

Accede a: `http://localhost:8000`

---

## ⚙ Configuración

Requisitos:

- Python 3.10+
- PostgreSQL 12+
- Redis 6+
- pip

Variables de entorno principales (`.env`):

| Variable | Descripción |
|----------|--------------|
| `SECRET_KEY` | Clave secreta de Django |
| `DEBUG` | Modo debug (`True`/`False`) |
| `DATABASE_URL` | Cadena de conexión a PostgreSQL |
| `REDIS_URL` | Cadena de conexión a Redis |
| `ALLOWED_HOSTS` | Hosts permitidos |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Credenciales SMTP para notificaciones |
| `POKEMON_TCG_API_KEY` | Clave de la API de Pokémon TCG |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Credenciales OAuth de Google |

---

## ⏱ Tareas Periódicas (Celery)

### `check_pokemon_prices` — cada 6 horas
Obtiene precios actuales desde la API de Pokémon TCG, los compara con las alertas configuradas por los usuarios y envía notificaciones cuando se cumplen las condiciones.

### `actualizar_pokedex_automatica` — diaria
Sincroniza datos de especies Pokémon y actualiza atributos TCG (rarezas, tipos, etc).

> Más detalles en [docs/CELERY.md](docs/CELERY.md).

---

## 🔌 API REST

```
GET    /api/cards/                     # Listar cartas (con filtros)
GET    /api/cards/{id}/                # Detalle de carta
GET    /api/cards/{id}/price-history/  # Histórico de precios
POST   /api/alerts/                    # Crear alerta
GET    /api/alerts/                    # Listar alertas del usuario
PUT    /api/alerts/{id}/               # Actualizar alerta
DELETE /api/alerts/{id}/               # Eliminar alerta
GET    /api/search/suggestions/        # Autocompletado de búsqueda
```

Documentación interactiva (Swagger UI): `http://localhost:8000/api/docs/`

---

## 🧪 Desarrollo y Calidad de Código

Antes de hacer commit:

```bash
python validate.py

# O por separado:
black cards alerts tasks users config tests
flake8 cards alerts tasks users config
pydocstyle cards alerts tasks users config
pytest
```

Tests con cobertura:

```bash
pytest --cov=cards --cov=alerts --cov=tasks --cov=users --cov-report=html
```

Todos los módulos, clases y funciones siguen el formato de docstrings de Google. Más detalles en [docs/CODE_QUALITY.md](docs/CODE_QUALITY.md).

---

## 📁 Estructura del Proyecto

```
pokealert/
├── cards/                     # Catálogo de cartas
│   ├── models.py              # Card, Rarity, Supertype, Subtype, Artist...
│   ├── views.py                
│   ├── serializers.py
│   ├── services/
│   │   ├── pokemontcg_service.py
│   │   ├── pricing.py
│   │   └── card_formatter.py
│   └── management/commands/
│       └── descargar_cartas_json.py
├── alerts/                    # Alertas de precio
│   ├── models.py              # PriceAlert, PriceHistory
│   ├── serializers.py
│   └── views.py
├── tasks/                     # Tareas Celery
│   ├── tasks.py                # check_pokemon_prices, actualizar_pokedex_automatica
│   └── views.py
├── users/                     # Autenticación y perfiles
│   ├── models.py
│   ├── views.py
│   └── forms.py
├── config/                    # Configuración del proyecto
│   ├── settings.py
│   ├── celery.py
│   └── urls.py
├── templates/
├── static/
├── tests/
├── docs/
│   ├── PROJECT_DOCUMENTATION.md
│   ├── CELERY.md
│   └── CODE_QUALITY.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .flake8
└── validate.py
```

---

## ☁ Despliegue

Desplegado en **Render** (plan gratuito) en [pokealert.onrender.com](https://pokealert.onrender.com), usando SQLite y Gunicorn.

- **Build command:** `pip install -r requirements.txt && python setup_db.py && python manage.py collectstatic --noinput`
- **Start command:** `gunicorn config.wsgi:application`

> **Nota:** en el plan gratuito de Render no hay worker ni scheduler de Celery activos, por lo que las tareas periódicas (y por tanto la actualización del histórico de precios) no se ejecutan automáticamente en producción. En local, todo el pipeline funciona con Celery Worker + Beat.

---

## 🩹 Problemas Comunes

### `ModuleNotFoundError: No module named 'django'`
```bash
# Asegúrate de que el entorno virtual esté activado
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

### `ConnectionError: Error -2 connecting to localhost:6379`
```bash
# Redis no está en ejecución
redis-server
# o con Docker:
docker run -d -p 6379:6379 redis:latest
```

### `ProgrammingError: relation 'cards_card' does not exist`
```bash
python manage.py migrate
python manage.py descargar_cartas_json
```

---

## 🚧 Roadmap

- [x] Autenticación con Google OAuth (django-allauth)
- [x] CI en GitHub Actions (ruff + pytest)
- [x] Refactor a arquitectura por capas de servicios
- [x] Histórico de precios con Celery Beat + Chart.js
- [x] Traducción ES→EN de nombres de cartas basada en Wikidex
- [x] Autocompletado con soporte de prefijos en español
- [ ] Worker/Beat de Celery en producción (plan de pago o alternativa)
- [ ] Dashboard con métricas agregadas de mercado
- [ ] Notificaciones push además de email
- [ ] Documentación de API ampliada (OpenAPI)

---

## 🤝 Contribuir

1. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
2. Realiza tus cambios y añade tests
3. Ejecuta la validación: `python validate.py`
4. Commit: `git commit -am "Agrega nueva funcionalidad"`
5. Push: `git push origin feature/nueva-funcionalidad`
6. Abre un Pull Request

---

## 👨‍💻 Autor

## Ángel Guerrero

**Backend Developer**

🐙 GitHub: [github.com/Dangelcrack](https://github.com/Dangelcrack)

---

## ⭐ ¿Te resulta útil?

Si este proyecto te ha sido de ayuda, considera dejarle una **⭐ Star** en GitHub.

---

## 📄 Licencia

Distribuido bajo la licencia **MIT**. Ver [LICENSE](LICENSE) para más detalles.
