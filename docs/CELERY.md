# Ejecutar Celery (worker + beat)

Estas instrucciones ayudan a ejecutar las tareas periódicas que actualizan precios (`check_pokemon_prices`) y mantener el histórico de precios.

Requisitos: Redis o RabbitMQ como broker (ejemplo usa Redis). Asegúrate de tener las variables de entorno necesarias como `POKEMON_TCG_API_KEY`.

Ejemplo (Redis local):

1. Instalar Redis (Windows: usar WSL o una instancia remota).
2. Instalar dependencias Python si no están:

```bash
pip install -r requirements.txt
```

3. Ejecutar worker:

```bash
celery -A config worker --loglevel=info
```

4. Ejecutar beat (programador):

```bash
celery -A config beat --loglevel=info
```

Alternativa sin Celery: existe un comando legacy `python manage.py check_prices` que puede ejecutarse desde el Programador de Tareas (Windows Task Scheduler) o cron.

Comando de ayuda para poblar históricos ausentes:

```bash
python manage.py generate_missing_price_history --days 30
```

Notas:
- Después de que la tarea actualice precios, la caché de `card_detail_{card_id}` se invalida automáticamente.
- Para entornos de producción, asegúrate de configurar `DEFAULT_FROM_EMAIL` y las credenciales de correo.
