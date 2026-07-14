#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

npm install
npx tailwindcss -i ./static/css/style.css -o ./static/css/style.min.css --minify

python manage.py collectstatic --no-input
python manage.py migrate