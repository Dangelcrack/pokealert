# PokeAlert — Documentación del Proyecto

## Resumen del proyecto

PokeAlert es una aplicación web construida con Django cuyo propósito es monitorizar precios de cartas Pokémon TCG, almacenar un histórico de precios y notificar a usuarios cuando se alcanzan condiciones de alerta. La aplicación combina datos locales (JSON y base de datos) y datos de la API pública de Pokémon TCG para presentar detalles de carta, gráficos de evolución de precio y configuraciones de alertas.

## Componentes principales

- `cards`: gestión de cartas, búsqueda, formato de datos y vistas públicas (detalle de carta, búsquedas). Contiene servicios de integración con la API externa y utilidades de normalización.
- `alerts`: modelos y vistas relacionados con alertas de precio y el modelo `PriceHistory` que almacena puntos históricos por carta.
- `tasks`: tareas periódicas (Celery) encargadas de refrescar precios, poblar `PriceHistory` y enviar notificaciones por correo.
- `templates`: vistas del frontend, entre ellas `card_detail.html` que renderiza el gráfico de evolución de precios mediante Chart.js.
- `config`: configuración del proyecto y enrutado principal.

## Estructura de carpetas (resumen)

- `cards/` — modelos (`Card`), vistas (`card_detail`, `search`), servicios (`services/`), comandos de gestión y utilidades.
- `alerts/` — `PriceAlert`, `PriceHistory`, API REST (viewsets) y el comando legacy `check_prices`.
- `tasks/` — tareas Celery (p. ej. `check_pokemon_prices`).
- `templates/` — plantillas Jinja2 para frontend.
- `docs/` — documentación del proyecto (aquí).

## Flujo de datos (precio → gráfico)

1. Origen del precio
   - Precios en la API de PokéTCG (`fetch_card`, `fetch_cards`) o en `todas_las_cartas_tcg.json` (repositorio local).
   - Las variantes de precio que se consultan incluyen `holofoil`, `normal` y `reverseHolofoil`; se toma el campo `market` cuando está disponible.

2. Persistencia y sincronización
   - Al visitar la vista de detalle (`card_detail`) el sistema aplica una estrategia: caché → DB local → JSON local → API externa.
   - Si se obtiene un precio válido y no existe un punto histórico en la fecha actual, se crea un registro `PriceHistory` (modelo en `alerts.models`).
   - Existe además una tarea periódica (`check_pokemon_prices` en `tasks/tasks.py`) que recorre cartas, obtiene precios vía API, actualiza `Card.price` y añade puntos en `PriceHistory` (evita duplicados del mismo día).

3. Exposición al frontend
   - La ruta `api/card/<card_id>/price-history/` devuelve fechas y precios de los últimos 30 días en JSON.
   - `card_detail.html` consume esa API y renderiza un gráfico usando Chart.js.

## Caché y efectos secundarios

- La vista de detalle usa un TTL de caché para el contexto (`card_detail_{card_id}`). Cuando la respuesta se sirve desde la caché, la lógica original se saltaba la creación del punto histórico para el día, lo que podía causar que el gráfico no tuviera datos recientes.
- Para mitigar esto se han aplicado varias medidas:
  - Al servir desde caché, si el contexto contiene un `market_price` válido y no existe `PriceHistory` para hoy, se crea ese punto histórico y se invalida la caché para forzar la próxima recarga fresca.
  - Cuando la tarea periódica actualiza el precio de una carta, invalida la clave de caché `card_detail_{card_id}` para que la vista muestre datos actualizados.

## Tareas periódicas y ejecución (Celery)

- Tarea principal: `check_pokemon_prices` (en `tasks/tasks.py`).
- Requisitos: broker (Redis o RabbitMQ) y configuración de Celery en `config/celery.py`.
- Comandos de ejemplo:

```bash
pip install -r requirements.txt
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

- Alternativa sin Celery: existe el comando de management `check_prices` (legacy) que puede ejecutarse desde el programador del sistema.

## Comandos de gestión útiles

- `python manage.py check_prices` — comando alternativo para comprobar precios y enviar correos.
- `python manage.py generate_missing_price_history [--days N]` — nuevo comando que crea puntos de `PriceHistory` usando `Card.price` para cartas que no tienen histórico (si `--days N` sólo crea para cartas sin histórico en los últimos N días).

## Pruebas

- La suite de tests se ejecuta con `pytest` (ver `pytest.ini` y `tests/`). Se recomienda ejecutar:

```bash
pytest -q
```

## Despliegue y consideraciones operativas

- Variables de entorno importantes:
  - `POKEMON_TCG_API_KEY` — clave para la API de Pokémon TCG.
  - `DEFAULT_FROM_EMAIL` — remitente para notificaciones por correo.
- Para producción usar un broker persistente (Redis o RabbitMQ) y configurar workers Celery y `beat` como servicios.
- Monitoreo recomendado: logs de Celery, métricas de errores HTTP de la API externa y alertas de errores en `check_pokemon_prices`.

## Diagnóstico rápido: gráfico de precio vacío

Pasos para reproducir y diagnosticar:

1. Comprobar si hay `PriceHistory` para la carta:

```python
python manage.py shell
>>> from alerts.models import PriceHistory
>>> PriceHistory.objects.filter(card__pokemontcg_id='ID_CARTA').exists()
```

2. Forzar ejecución de la tarea de actualización (local):

```bash
python manage.py check_prices
# o ejecutar el worker/beat de Celery en local
```

3. Ejecutar el comando de rellenado si faltan datos históricos:

```bash
python manage.py generate_missing_price_history --days 30
```

4. Ver logs del servidor y de Celery en busca de errores relacionados con la API externa o errores de parsing.

## Recomendaciones y próximos pasos

- Producción: desplegar workers Celery y `beat` y asegurar el broker.
- Observabilidad: añadir métricas (conteo de puntos creados, errores de API) y trazabilidad por carta (`card_id` en logs estructurados).
- Caché: parametrizar el TTL de `card_detail` en `settings` y documentar la política de invalidación; actualmente se invalida en actualizaciones, pero es útil controlar el TTL desde configuración.
- Robustez: mejorar `extract_market_price` para aceptar más variantes y fuentes de precio (ej. `mid` si `market` no existe) y añadir tests que cubran respuestas parciales de la API.

## Cambios recientes (implementados)

- Se añadió creación de `PriceHistory` cuando la vista `card_detail` se sirve desde caché y falta el punto histórico del día; la caché se invalida tras crear el punto.
- La tarea `check_pokemon_prices` invalida la caché por carta después de actualizar `Card.price`.
- Se añadió el comando `generate_missing_price_history` para poblar históricos ausentes.
- Se añadió documentación de Celery en `docs/CELERY.md`.

## Contacto del repositorio

Para cualquier cambio o despliegue, use el flujo de git del equipo (branch → PR → revisión → merge). Incluya referencias a ticket o issue que justifiquen cambios en la política de caché o en tareas periódicas.
