#!/usr/bin/env bash
set -o errexit

# 1. Instalar dependencias de Python
pip install -r requirements.txt

# 2. Instalar Node y compilar Tailwind DIRECTO en el style.css
npm install
npx tailwindcss -i ./static/css/style.css -o ./static/css/style.css --minify

# 3. Preparar estáticos de Django y migraciones
python manage.py collectstatic --no-input
python manage.py migrate