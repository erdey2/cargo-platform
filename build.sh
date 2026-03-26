#!/usr/bin/env bash
set -o errexit  # stop on error

pip install --upgrade pip
pip install -r requirements/production.txt

python -m pip install gunicorn daphne

python manage.py collectstatic --noinput
python manage.py migrate
