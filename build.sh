#!/usr/bin/env bash

pip install --upgrade pip
pip install -r requirements/production.txt

python manage.py collectstatic --noinput
python manage.py migrate
