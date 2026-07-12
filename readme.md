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
- [Tareas Periódicas](#-tareas-periódicas)
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

✅ Histórico de precios con gráficos interactivos (Chart.js), actualizado también en producción.

✅ Sincronización automática con la API de Pokémon TCG.

✅ Autenticación de usuarios, incluyendo login con Google (OAuth vía django-allauth).

✅ Notificaciones por email cuando una alerta se activa.

✅ API REST documentada con Swagger para integraciones externas.

✅ Tareas periódicas con Celery + Beat en local, y endpoints HTTP + cron externo en producción (ver [Tareas Periódicas](#-tareas-periódicas)).

✅ Suite de tests y linting automatizado (ruff, black, flake8, pydocstyle) con CI en GitHub Actions.

---

## 🚀 Tecnologías

| Tecnología | Uso |
|------------|-----|
| Python / Django | Backend y lógica de negocio |
| Django REST Framework | API REST |
| PostgreSQL | Base de datos (SQLite en despliegue de demo) |
| Celery + Redis | Tareas periódicas y caché (entorno local) |
| cron-job.org | Disparo de tareas periódicas en producción |
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
   ┌─────────────────────┬─────────────────────────────────┐
   │   Local              │   Producción (Render free)       │
   │ Celery Beat ──6h──►   │ cron-job.org ──24h──► endpoint   │
   │ check_pokemon_prices  │ /api/tasks/check-prices/         │
   └─────────────────────┴─────────────────────────────────┘
       │
       ▼
PriceHistory / Alertas
       │
       ▼
Django REST API
       │
       ▼
Frontend (Tailwind + Chart.js) / Notificaciones por email
```

El proyecto está organizado en apps Django independientes por dominio: `cards` (catálogo), `alerts` (alertas y notificaciones), `tasks` (tareas periódicas) y `users` (autenticación y perfiles).

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

Genera un `CRON_SECRET_TOKEN` (protege los endpoints de disparo manual de tareas):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
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
| `CRON_SECRET_TOKEN` | Token que protege los endpoints `/api/tasks/*` usados por el cron externo |

---

## ⏱ Tareas Periódicas

### En local: Celery + Beat

- **`check_pokemon_prices`** (cada 6h): obtiene precios actuales desde la API de Pokémon TCG, los compara con las alertas configuradas por los usuarios y envía notificaciones cuando se cumplen las condiciones.
- **`actualizar_pokedex_automatica`** (diaria): sincroniza datos de especies Pokémon y actualiza atributos TCG (rarezas, tipos, etc).

> Más detalles en [docs/CELERY.md](docs/CELERY.md).

### En producción: endpoints HTTP + cron externo

El plan gratuito de Render no permite mantener un worker ni un scheduler de Celery corriendo en segundo plano. Para resolverlo sin salir del free tier, ambas tareas están expuestas como endpoints HTTP que las ejecutan de forma síncrona, protegidos por token:

```
GET /api/tasks/check-prices/?token=<CRON_SECRET_TOKEN>
GET /api/tasks/update-pokedex/?token=<CRON_SECRET_TOKEN>
```

Un cronjob gratuito en **cron-job.org** llama a `check-prices` una vez al día, disparando la actualización de precios y del histórico en producción sin necesidad de Celery Worker/Beat activos. El propio código evita duplicar entradas de histórico si la tarea se ejecutara más de una vez el mismo día.

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
GET    /api/tasks/check-prices/        # Dispara check_pokemon_prices (requiere token)
GET    /api/tasks/update-pokedex/      # Dispara actualizar_pokedex_automatica (requiere token)
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
├── tasks/                     # Tareas periódicas
│   ├── tasks.py                # check_pokemon_prices, actualizar_pokedex_automatica
│   ├── views.py                # Endpoints HTTP para disparo vía cron externo
│   └── urls.py
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

> **Nota:** el plan gratuito de Render no permite tener Celery Worker ni Beat corriendo en segundo plano. Para no perder la actualización periódica de precios en producción, las tareas se exponen como endpoints HTTP protegidos por token y se disparan mediante un cronjob externo gratuito (cron-job.org), una vez al día. Ver [Tareas Periódicas](#-tareas-periódicas) para el detalle. En local, todo el pipeline sigue funcionando con Celery Worker + Beat sin cambios.

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

### `ModuleNotFoundError: No module named 'tasks.urls'`
```bash
# Falta el archivo tasks/urls.py, o está en la ruta incorrecta.
# Debe existir en tasks/urls.py, al mismo nivel que tasks/tasks.py y tasks/views.py
```

---

## 🚧 Roadmap

- [x] Autenticación con Google OAuth (django-allauth)
- [x] CI en GitHub Actions (ruff + pytest)
- [x] Refactor a arquitectura por capas de servicios
- [x] Histórico de precios con Celery Beat + Chart.js
- [x] Traducción ES→EN de nombres de cartas basada en Wikidex
- [x] Autocompletado con soporte de prefijos en español
- [x] Actualización de precios en producción sin Celery Worker/Beat (endpoints HTTP + cron-job.org)
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
