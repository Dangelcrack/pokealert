import os
import django
from django.core.management import execute_from_command_line

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User  # noqa: E402

# Ejecutar migraciones
print("🔄 Ejecutando migraciones...")
execute_from_command_line(['manage.py', 'migrate'])

# Crear superuser
if not User.objects.filter(username='admin').exists():
    print("👤 Creando superuser admin...")
    User.objects.create_superuser('admin', 'admin@pokealert.com', 'admin123456')
    print("✅ Superuser 'admin' creado")
else:
    print("✅ Superuser ya existe")