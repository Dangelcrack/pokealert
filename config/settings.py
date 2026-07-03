# config/settings.py (PRODUCCIÓN)
"""
Django settings for config project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno
load_dotenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-fallback-si-no-hay-env")

DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY", "")

SITE_ID = 1

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_filters",
    "rest_framework",
    "cards",
    "alerts",
    "tasks",
    "users",

    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "allauth.account.middleware.AccountMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ===================== DATABASE =====================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
    }
}

# ===================== PASSWORD VALIDATION =====================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ===================== INTERNATIONALIZATION =====================
LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

# ===================== STATIC FILES =====================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# ===================== DEFAULT AUTO FIELD =====================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ===================== REST FRAMEWORK =====================
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

# ===================== CELERY =====================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "False") == "True"

# ===================== EMAIL CONFIGURATION =====================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = f"PokeAlert <{EMAIL_HOST_USER}>"

# ===================== CELERY BEAT SCHEDULE =====================
CELERY_BEAT_SCHEDULE = {
    "actualizar-pokedex-mensual": {
        "task": "tasks.tasks.actualizar_pokedex_automatica",
        "schedule": crontab(day_of_month=1, hour=0, minute=0),
    },
    "verificar-alertas-precios-diario": {
        "task": "tasks.tasks.check_pokemon_prices",
        "schedule": crontab(hour=2, minute=0),
    },
}

# ===================== SECURITY =====================
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
).split(",")

# En producción con HTTPS
if not DEBUG:
    SECURE_SSL_REDIRECT = False  # AlwaysData maneja SSL
    SESSION_COOKIE_SECURE = False  # AlwaysData maneja cookies
    CSRF_COOKIE_SECURE = False
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_SECURITY_POLICY = {
        "default-src": ("'self'",),
    }

# ===================== LOGGING =====================
LOGS_DIR = BASE_DIR / "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "pokealert.log",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "tasks.tasks": {  # ✅ Registramos el logger de tu app encargada del backend distribuido
            "handlers": ["file", "console"],
            "level": "INFO",
        },
        "alerts.tasks": {
            "handlers": ["file", "console"],
            "level": "INFO",
        },
    },
}

# ===================== DJANGO ALLAUTH =====================

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# El nuevo estándar para definir cómo se inicia sesión (reemplaza a ACCOUNT_AUTHENTICATION_METHOD)
ACCOUNT_LOGIN_METHODS = {"username", "email"}

# El nuevo estándar para exigir campos en el registro (reemplaza a EMAIL_REQUIRED y USERNAME_REQUIRED)
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]

ACCOUNT_EMAIL_VERIFICATION = "none"

# Configuración de inicio de sesión social automático por Email
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_LOGIN_ON_GET = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}