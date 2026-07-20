# PokéAlert — Documentación del Proyecto

## Resumen del proyecto

**PokéAlert** es una aplicación web desarrollada con **Django** cuyo propósito es monitorizar precios de cartas **Pokémon TCG**, almacenar un histórico de precios y notificar a los usuarios cuando se cumplen determinadas condiciones de alerta.

La aplicación combina datos procedentes de:

- La API pública de Pokémon TCG.
- Datos locales almacenados en archivos JSON.
- Base de datos propia.

Con ello ofrece:

- Búsqueda de cartas.
- Página de detalle de cada carta.
- Historial de precios.
- Gráficos de evolución mediante Chart.js.
- Alertas automáticas por correo electrónico.

---

# Componentes principales

## `cards`

Responsable de toda la gestión relacionada con las cartas Pokémon.

Incluye:

- Modelo `Card`
- Búsquedas
- Vista `card_detail`
- Integración con la API de Pokémon TCG
- Normalización de datos
- Servicios auxiliares

---

## `alerts`

Gestiona todo el sistema de alertas.

Contiene:

- Modelo `PriceAlert`
- Modelo `PriceHistory`
- API REST
- Envío de emails mediante **SendGrid** usando **django-anymail**

---

## `tasks`

Gestiona las tareas periódicas del proyecto.

En desarrollo utiliza **Celery**.

En producción (Render) utiliza endpoints HTTP protegidos por token para ser ejecutados mediante un servicio de cron externo.

Sus funciones principales son:

- Actualizar precios.
- Poblar el histórico.
- Evaluar alertas.
- Actualizar la Pokédex automáticamente.

---

## `templates`

Contiene las plantillas del frontend.

Especialmente:

- `card_detail.html`

Desde esta plantilla se renderiza el gráfico de evolución del precio utilizando **Chart.js**.

---

## `config`

Configuración principal del proyecto:

- Settings
- URLs
- Celery
- Configuración global

---

## `docs`

Documentación técnica del proyecto.

---

# Estructura de carpetas

```text
cards/
│
├── models.py
├── views.py
├── services/
├── management/
└── utils/

alerts/
│
├── models.py
├── viewsets.py
└── email/

tasks/
│
├── tasks.py
└── views.py

templates/
│
└── card_detail.html

config/

docs/
```

---

# Flujo de datos

## Precio → Histórico → Gráfico → Alertas

### 1. Obtención del precio

El sistema intenta obtener el precio desde varias fuentes.

Orden de prioridad:

1. Caché
2. Base de datos
3. JSON local
4. API Pokémon TCG

Las variantes consultadas son:

- `holofoil`
- `normal`
- `reverseHolofoil`

Siempre que existe se utiliza el valor:

```python
market
```

---

### 2. Persistencia

Cuando se accede a la vista:

```python
card_detail
```

se sigue la estrategia:

```
Caché
      ↓
Base de datos
      ↓
JSON local
      ↓
API externa
```

Si se obtiene un precio válido:

- Se actualiza `Card.price`.
- Si todavía no existe un registro para el día actual, se crea un nuevo objeto:

```python
PriceHistory
```

---

### 3. Sincronización automática

Existe una tarea periódica:

```python
check_pokemon_prices
```

ubicada en:

```text
tasks/tasks.py
```

Esta tarea:

- Recorre todas las cartas.
- Consulta la API.
- Actualiza `Card.price`.
- Añade un nuevo punto a `PriceHistory`.
- Evita duplicados del mismo día.
- Evalúa las alertas activas de los usuarios.

---

### 4. Exposición al frontend

Existe un endpoint:

```text
/api/card/<card_id>/price-history/
```

Devuelve un JSON con:

- Fechas
- Precios

correspondientes a los últimos 30 días.

---

### 5. Representación gráfica

La plantilla:

```text
card_detail.html
```

consume dicha API y genera un gráfico mediante:

- Chart.js

---

### 6. Notificaciones

Cuando una alerta se dispara:

- Se envía un correo mediante SendGrid.
- Se utiliza la API HTTPS.
- La integración se realiza mediante:

```text
django-anymail
```

Este enfoque evita los bloqueos de SMTP presentes en Render.

---

# Caché

La vista:

```python
card_detail
```

utiliza una caché con una clave similar a:

```text
card_detail_<card_id>
```

con un tiempo de vida (TTL).

## Problema detectado

Cuando la página se servía desde la caché:

- No se ejecutaba la lógica de creación del histórico.
- El gráfico podía quedarse sin datos recientes.

---

## Solución implementada

Cuando la respuesta procede de la caché:

1. Se comprueba si existe:

```python
market_price
```

2. Si no existe un `PriceHistory` para hoy:

- Se crea automáticamente.

3. Después:

- Se invalida la caché para forzar una recarga completa en la siguiente petición.

---

## Invalidación de caché

Cada vez que una tarea actualiza:

```python
Card.price
```

también elimina la clave:

```text
card_detail_<card_id>
```

para que el usuario vea inmediatamente el precio actualizado.

---

# Tareas periódicas

## Desarrollo (Celery)

Tarea principal:

```python
check_pokemon_prices
```

Ubicación:

```text
tasks/tasks.py
```

Requisitos:

- Redis o RabbitMQ
- Celery

Configuración:

```text
config/celery.py
```

### Comandos

```bash
pip install -r requirements.txt

celery -A config worker --loglevel=info

celery -A config beat --loglevel=info
```

---

# Producción (Render)

El plan gratuito de Render presenta varias limitaciones:

- No permite workers permanentes.
- No permite Celery Beat.
- Bloquea SMTP (25, 465 y 587).

---

## Solución

Las tareas se exponen mediante endpoints HTTP protegidos por un token secreto.

El trabajo real se ejecuta en un hilo en segundo plano para responder inmediatamente y evitar timeouts.

---

## Endpoints

Actualizar precios:

```text
GET /api/tasks/check-prices/?token=<CRON_SECRET_TOKEN>
```

Actualizar Pokédex:

```text
GET /api/tasks/update-pokedex/?token=<CRON_SECRET_TOKEN>
```

---

## Cron externo

En producción se utiliza:

- cron-job.org

Este servicio realiza una petición HTTP diaria al endpoint de actualización.

Gracias a ello:

- Se mantienen sincronizados los precios.
- Se generan históricos.
- Se evalúan alertas.
- No es necesario disponer de Celery en producción.

---

# Comandos de gestión

Comprobar precios manualmente:

```bash
python manage.py check_prices
```

---

Generar históricos inexistentes:

```bash
python manage.py generate_missing_price_history
```

También admite:

```bash
python manage.py generate_missing_price_history --days 30
```

Solo crea históricos para cartas que no tengan registros recientes.

---

# Pruebas

La aplicación utiliza **pytest**.

Ejecutar:

```bash
pytest -q
```

---

# Variables de entorno

Variables necesarias en producción.

## Pokémon TCG

```env
POKEMON_TCG_API_KEY=
```

---

## SendGrid

```env
EMAIL_BACKEND=anymail.backends.sendgrid.EmailBackend

SENDGRID_API_KEY=

EMAIL_FROM=
```

---

## Seguridad

```env
CRON_SECRET_TOKEN=
```

---

# Monitorización recomendada

Se recomienda revisar periódicamente:

- Logs de Render.
- Errores HTTP de la API Pokémon.
- Estado de SendGrid.
- Ejecuciones del cron.
- Alertas enviadas.

---

# Diagnóstico rápido

## El gráfico aparece vacío

Comprobar si existe histórico.

```bash
python manage.py shell
```

```python
from alerts.models import PriceHistory

PriceHistory.objects.filter(
    card__pokemontcg_id="ID_CARTA"
).exists()
```

---

## Forzar actualización

Local:

```bash
python manage.py check_prices
```

Producción:

```text
GET /api/tasks/check-prices/?token=<TOKEN>
```

---

## Generar históricos

```bash
python manage.py generate_missing_price_history --days 30
```

---

## Revisar logs

Buscar posibles errores relacionados con:

- API Pokémon TCG
- SendGrid
- Parseo de precios
- Timeouts
- Cron

---

# Recomendaciones futuras

## Observabilidad

Añadir métricas como:

- Número de puntos creados.
- Errores de API.
- Correos enviados.
- Correos fallidos.
- Tiempo medio de actualización.

---

## Caché

- Parametrizar el TTL desde `settings.py`.
- Documentar completamente la política de invalidación.

---

## Robustez

Mejorar:

```python
extract_market_price()
```

para aceptar más variantes:

- market
- mid
- low
- average
- futuras fuentes de precio

---

# Cambios recientes

Se han implementado las siguientes mejoras:

- Migración completa del sistema SMTP tradicional a SendGrid mediante API HTTPS.
- Integración de **django-anymail**.
- Compatibilidad con el plan gratuito de Render.
- Sustitución de Celery en producción por endpoints HTTP protegidos.
- Ejecución mediante cron-job.org.
- Evaluación de alertas utilizando `Card.price`.
- Eliminación de la dependencia del deduplicado diario para disparar alertas.
- Creación automática de `PriceHistory` cuando una página se sirve desde la caché.
- Invalidación automática de la caché tras crear el histórico.
- Incorporación del comando:

```bash
python manage.py generate_missing_price_history
```

para poblar históricos masivamente.

---

# Contacto y flujo de trabajo

Para cualquier modificación del proyecto debe seguirse el flujo Git establecido por el equipo:

```
Branch
      ↓
Pull Request
      ↓
Revisión
      ↓
Merge
```

Siempre que sea posible, cada cambio deberá estar asociado a una **Issue** que justifique modificaciones relacionadas con:

- Caché.
- Envío de correo.
- Tareas periódicas.
- Integraciones externas.
- Arquitectura del sistema.